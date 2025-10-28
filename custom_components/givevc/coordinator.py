from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import ModbusTcpClient
import logging
from datetime import datetime, timedelta, timezone


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

        # Ensure update_interval is a timedelta
        update_interval_td = (
            timedelta(seconds=scan_interval)
            if isinstance(scan_interval, (int, float))
            else scan_interval
        )

        super().__init__(
            hass,
            _LOGGER,
            name="Modbus Coordinator",
            update_interval=update_interval_td,
        )

        self.last_success = True  # Track connection status

    async def _async_update_data(self):
        try:
            ####### Do I need to make two calls 60 + 55 and combine?
            result = await self.hass.async_add_executor_job(
                lambda: self.client.read_holding_registers(
                    0, count=60)
            )
            result2 = await self.hass.async_add_executor_job(
                lambda: self.client.read_holding_registers(
                    60, count=55)
            )
            if result.isError() or result2.isError():
                self.last_success = False
                self.failure_count += 1
                self.total_retries += 1
                raise UpdateFailed("Modbus read failed")
            self.last_success = True
            self.last_success_time = datetime.now(timezone.utc)
            self.failure_count = 0
            allregisters=result.registers + result2.registers
            return allregisters
        except Exception as e:
            self.last_success = False
            self.failure_count += 1
            self.total_retries += 1
            raise UpdateFailed("Modbus read exception")
