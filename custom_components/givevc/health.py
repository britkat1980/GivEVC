from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ModbusHealthSensor(coordinator)])

class ModbusHealthSensor(SensorEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Modbus Connection Health"
        self._attr_icon = "mdi:lan-connect"

    @property
    def unique_id(self):
        return f"modbus_health_{self.coordinator.client.host}"

    @property
    def state(self):
        return "connected" if self.coordinator.last_success else "disconnected"

    @property
    def device_class(self):
        return "connectivity"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"modbus_{self.coordinator.unit_id}_{self.coordinator.client.host}")},
            "name": f"Modbus @ {self.coordinator.client.host}",
            "manufacturer": "Modbus",
            "model": "Generic Modbus TCP"
        }