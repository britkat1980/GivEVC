import ipaddress
import logging
from datetime import datetime,timedelta, timezone


from pymodbus.client import ModbusTcpClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GivEVCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self.async_step_scan_start()

    async def async_step_scan_start(self, user_input=None):
        # Start the scanning coroutine as a background task and pass it
        # to async_show_progress so Home Assistant can track progress and
        # resume the flow when the task is done.
        self.hass.data.setdefault(DOMAIN, {})
        self.hass.data[DOMAIN]["scan_start_time"] = datetime.now(timezone.utc)

        scan_task = self.hass.async_create_task(
            self._scan_subnet_for_modbus(),
            "Scan Modbus subnet",
        )

        return self.async_show_progress(
            step_id="scan_progress",
            progress_action="scan_modbus",
            progress_task=scan_task,
            # description_placeholders=["Scanning your network for Modbus devices…",""]
        )

    async def async_step_scan_progress(self, user_input=None):
        # Check the progress task that was created in async_step_scan_start
        progress_task = self.async_get_progress_task()
        start_time = self.hass.data.get(DOMAIN, {}).get("scan_start_time")
        timeout = timedelta(seconds=15)  # adjust as needed

        if start_time and datetime.now(timezone.utc) - start_time > timeout:
            _LOGGER.warning("Modbus scan timed out")
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({
                    vol.Required("host"): str,
                    vol.Required("scan_interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600))
                }),
                errors={"base": "scan_timeout"}
            )

        if progress_task is None or not progress_task.done():
            return self.async_show_progress(
                step_id="scan_progress",
                progress_action="scan_modbus",
                progress_task=progress_task,
            )



        # Task finished, pull the result (handle exceptions)
        try:
            found = progress_task.result()
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Error while scanning for Modbus devices: %s", err)
            found = []

        # Store the scan results on the flow instance for the next step
        self._scan_found = found

        # Transition the flow: indicate progress is done and point to next step
        next_step = "confirm" if found else "manual"
        return self.async_show_progress_done(next_step_id=next_step)

    async def async_step_confirm(self, user_input=None):
        # If user_input is None, show the confirmation form using the
        # stored scan results. When provided, create the entry.
        if user_input is None:
            found = getattr(self, "_scan_found", [])
            options = {ip: f"{ip} ({serial})" for ip, serial in found}
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required("host", default=list(options.keys())[0]): vol.In(
                            options
                        ),
                        vol.Required("scan_interval", default=30): vol.All(
                            vol.Coerce(int), vol.Range(min=5, max=3600)
                        ),
                    }
                ),
            )

        serial = await self.hass.async_add_executor_job(
            get_modbus_serial, user_input["host"]
        )

        user_input["serial"] = serial
        return self.async_create_entry(
            title=f"GivEVC ({serial})" if serial else f"GivEVC @ {user_input['host']}",
            data=user_input,
        )

    async def async_step_manual(self, user_input=None):
        # If coming from a failed scan, show the manual form. Otherwise,
        # create the entry when user_input is provided.
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema(
                    {
                        vol.Required("host"): str,
                        vol.Required("scan_interval", default=30): vol.All(
                            vol.Coerce(int), vol.Range(min=10, max=3600)
                        ),
                    }
                ),
            )

        serial = await self.hass.async_add_executor_job(
            get_modbus_serial, user_input["host"]
        )
        user_input["serial"] = serial
        return self.async_create_entry(
            title=f"GivEVC ({serial})" if serial else f"GivEVC ({user_input['host']})",
            data=user_input,
        )

    async def _scan_subnet_for_modbus(self):
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            resp = await session.get("http://supervisor/network/info")
            data = await resp.json()
            iface = data["interfaces"][0]
            cidr = iface["ipv4"]["address"]
            ip, mask = cidr.split("/")
            network = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
        except Exception as e:
            _LOGGER.warning(f"Supervisor resp: {resp}")
            _LOGGER.warning(f"Supervisor network info failed: {e}")

        # Get subnet from docker if not addon
        if network == None:
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0)
                # doesn't even have to be reachable
                s.connect(('10.254.254.254', 1))
                ip = s.getsockname()[0]
                s.close()
                network = ipaddress.ip_network(f"{ip}/24", strict=False)
            except Exception as e:
                _LOGGER.warning(f"Docker network info failed: {e}")
                return []

        found = []
        for host in network.hosts():
            ip_str = str(host)
            try:
                sock = socket.create_connection((ip_str, 502), timeout=0.5)
                sock.close()
                serial = get_modbus_serial(ip_str)
                if serial:
                    found.append((ip_str, serial))
            except Exception:
                continue

        return found


def get_modbus_serial(ip, unit_id=1):
    try:
        client = ModbusTcpClient(ip)
        result = client.read_holding_registers(38, count=32, device_id=unit_id)
        client.close()

        if result.isError() or not result.registers:
            return None
        serial = ""
        for reg in result.registers:
            if not reg == 0:
                serial = serial + chr(reg)
        return serial if serial else None
    except Exception:
        return None
