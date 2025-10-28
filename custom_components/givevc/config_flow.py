import ipaddress
import logging
import socket

from pymodbus.client import ModbusTcpClient
import voluptuous as vol
import json
from pathlib import Path

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

        # If no task is registered or task is not done yet, keep showing progress
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

        # Prepare entry data and include register map loaded from file
        data = dict(user_input)
        data["serial"] = serial

        try:
            reg_file = Path(__file__).parent / "register_map.json"
            with reg_file.open() as f:
                reg_map = json.load(f)
        except Exception:  # pragma: no cover - best effort
            _LOGGER.debug(
                "No register_map.json found or failed to load; continuing without map"
            )
            reg_map = []

        # Normalize register values (strings to ints where appropriate)
        parsed_map = []
        for cfg in reg_map:
            cfg_copy = dict(cfg)
            reg_raw = cfg_copy.get("register")
            try:
                if isinstance(reg_raw, str):
                    cfg_copy["register"] = int(reg_raw, 0)
            except Exception:
                _LOGGER.debug("Invalid register value in map: %s", reg_raw)
            parsed_map.append(cfg_copy)

        data["register_map"] = parsed_map

        return self.async_create_entry(
            title=f"GivEVC ({serial})" if serial else f"GivEVC @ {user_input['host']}",
            data=data,
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
        # Prepare entry data and include register map loaded from file
        data = dict(user_input)
        data["serial"] = serial

        try:
            reg_file = Path(__file__).parent / "register_map.json"
            with reg_file.open() as f:
                reg_map = json.load(f)
        except Exception:  # pragma: no cover - best effort
            _LOGGER.debug(
                "No register_map.json found or failed to load; continuing without map"
            )
            reg_map = []

        parsed_map = []
        for cfg in reg_map:
            cfg_copy = dict(cfg)
            reg_raw = cfg_copy.get("register")
            try:
                if isinstance(reg_raw, str):
                    cfg_copy["register"] = int(reg_raw, 0)
            except Exception:
                _LOGGER.debug("Invalid register value in map: %s", reg_raw)
            parsed_map.append(cfg_copy)

        data["register_map"] = parsed_map

        return self.async_create_entry(
            title=f"GivEVC ({serial})" if serial else f"GivEVC ({user_input['host']})",
            data=data,
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
            _LOGGER.warning(f"Supervisor network info failed: {e}")
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
