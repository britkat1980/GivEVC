import socket
import logging
import ipaddress
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN
from pymodbus.client import ModbusTcpClient
from .findEVC import findEVC

_LOGGER = logging.getLogger(__name__)

class ModbusBlockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            serial = await self.hass.async_add_executor_job(
            get_modbus_serial, user_input["host"]
            )
            user_input["serial"] = serial
            if serial:
                return self.async_create_entry(
                    title=f"GivEVC ({serial})",
                    data=user_input,
                    )
            else:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required("host"): str,
                        vol.Required("scan_interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600))
                    }),
                    errors={"base": "IP Address is not as valid GivEVC device"}
                )

        found = await scan_subnet_for_modbus(self)
        if found:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("host"): (found),
                    vol.Required("scan_interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600))
                })
            )
        else:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("host"): str,
                    vol.Required("scan_interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600))
                }),
                errors={"base": "No Devices found on subnet, please enter manually"}
            )

def get_modbus_serial(ip):
    try:
        client = ModbusTcpClient(ip)
        result = client.read_holding_registers(38, count=32)
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

async def scan_subnet_for_modbus(self):
    network={}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
        #network = ipaddress.ip_network("192.168.2.1/24", strict=False)
        _LOGGER.warning(f"Network found: {network}")
    except Exception as e:
        _LOGGER.warning(f"Docker network info failed: {e}")
        return []

    serial = []
    evc=findEVC(network)
    for ip in evc:
        serial=get_modbus_serial(evc[ip])
        if serial:
            _LOGGER.warning(f"Found GivEVC {serial} at IP: {evc[ip]}")
            return evc[ip]
    return []