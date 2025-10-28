from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helpers import decode_float, decode_signed_16, decode_signed_32


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")

    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusSensorEntity(coordinator, config, serial)
        for config in register_map if config["type"] == "sensor"
    ]
    async_add_entities(entities)


class ModbusSensorEntity(SensorEntity):
    def __init__(self, coordinator, config, serial):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config["name"]
        self._register = config["register"]
        self._scale = config.get("scale", 1.0)
        self._unit = config.get("unit", "")
        self._float = config.get("float", False)
        self._signed = config.get("signed", False)
        self._byte_order = config.get("byte_order", "ABCD")
        self._device_class = config.get("device_class")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"givevc_{self.serial}")},
            "name": "GivEVC",
            "manufacturer": "GivEnergy",
            "model": "GivEVC",
    }

    @property
    def unique_id(self):
        return f"{self.serial}_{self._attr_name.lower().replace(' ', '_')}"

    @property
    def native_unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class

    @property
    def state(self):
        try:
            data = self.coordinator.data
            if self._float:
                val = decode_float(data[self._register:self._register+2], self._byte_order)
            elif self._signed and self._register + 1 < len(data):
                val = decode_signed_32(data[self._register:self._register+2], self._byte_order)
            elif self._signed:
                val = decode_signed_16(data[self._register])
            else:
                val = data[self._register]
            return round(val * self._scale, 2)
        except Exception:
            return None