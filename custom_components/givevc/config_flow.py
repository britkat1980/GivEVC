import logging
import socket
import ipaddress
import voluptuous as vol
import struct

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from pymodbus.client import ModbusTcpClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self.async_step_scan_start()

    async def async_step_scan_start(self, user_input=None):
        return self.async_show_progress(
            step_id="scan_progress",
            progress_action="scan_modbus",
            description="Scanning your network for Modbus devices…"
        )

    async def async_step_scan_progress(self, user_input=None):
        found = await self._scan_subnet_for_modbus()

        if found:
            options = {ip: f"{ip} ({serial})" for ip, serial in found}
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({
                    vol.Required("host", default=list(options.keys())[0]): vol.In(options),
                    vol.Required("scan_interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600))
                })
            )
        else:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({
                    vol.Required("host"): str,
                    vol.Required("scan_interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600))
                }),
                errors={"base": "no_devices_found"}
            )

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            serial = await self.hass.async_add_executor_job(get_modbus_serial, user_input["host"])
            user_input["serial"] = serial
            return self.async_create_entry(
                title=f"Modbus @ {user_input['host']} ({serial})" if serial else f"Modbus @ {user_input['host']}",
                data=user_input
            )

    async def async_step_manual(self, user_input=None):
        if user_input is not None:
            serial = await self.hass.async_add_executor_job(get_modbus_serial, user_input["host"])
            user_input["serial"] = serial
            return self.async_create_entry(
                title=f"Modbus @ {user_input['host']} ({serial})" if serial else f"Modbus @ {user_input['host']}",
                data=user_input
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
        result = client.read_holding_registers(38, 32, unit=unit_id)
        client.close()

        if result.isError() or not result.registers:
            return None

        raw_bytes = b''.join(struct.pack(">H", reg) for reg in result.registers)
        serial = raw_bytes.decode("ascii", errors="ignore").strip()
        return serial if serial else None
    except Exception:
        return None