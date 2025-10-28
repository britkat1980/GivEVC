from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ModbusRetrySensor(coordinator),
        ModbusLastSuccessSensor(coordinator)
    ])

class ModbusRetrySensor(SensorEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Modbus Retry Count"
        self._attr_icon = "mdi:reload"

    @property
    def unique_id(self):
        return f"modbus_retry_{self.coordinator.client.host}"

    @property
    def state(self):
        return self.coordinator.failure_count

class ModbusLastSuccessSensor(SensorEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Modbus Last Success"
        self._attr_icon = "mdi:clock-check"

    @property
    def unique_id(self):
        return f"modbus_last_success_{self.coordinator.client.host}"

    @property
    def state(self):
        if self.coordinator.last_success_time:
            return self.coordinator.last_success_time.isoformat()
        return "never"