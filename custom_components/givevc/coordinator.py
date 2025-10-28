from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import ModbusTcpClient
import logging
from datetime import datetime


_LOGGER = logging.getLogger(__name__)

class ModbusCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host, port, unit_id, scan_interval, register_count):
        self.client = ModbusTcpClient(host, port=port)
        self.unit_id = unit_id
        self.register_count = register_count
        self.last_success = True
        self.last_success_time = None
        self.failure_count = 0
        self.total_retries = 0


        super().__init__(
            hass,
            _LOGGER,
            name="Modbus Coordinator",
            update_interval=scan_interval
        )

        self.last_success = True  # Track connection status

    async def _async_update_data(self):
        try:
            result = await self.hass.async_add_executor_job(
                self.client.read_holding_registers, 0, self.register_count, self.unit_id
            )
            if result.isError():
                self.last_success = False
                self.failure_count += 1
                self.total_retries += 1
                raise UpdateFailed("Modbus read failed")
            self.last_success = True
            self.last_success_time = datetime.utcnow()
            self.failure_count = 0
            return result.registers
        except Exception:
            self.last_success = False
            self.failure_count += 1
            self.total_retries += 1
            raise UpdateFailed("Modbus read exception")


