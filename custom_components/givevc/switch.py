from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")
    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusSwitchEntity(coordinator, config, serial)
        for config in register_map if config["type"] == "switch"
    ]
    async_add_entities(entities)


class ModbusSwitchEntity(SwitchEntity):
    def __init__(self, coordinator, config, serial):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config["name"]
        self._register = config["register"]
        self._mode = config.get("mode", "holding")
        self._invert = config.get("invert", False)
        self._write_on = config.get("write_on", 1)
        self._write_off = config.get("write_off", 0)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"givevc_{self.serial}")},
            "name": "GivEVC",
            "manufacturer": "GivEnergy",
            "model": "GivEVC",
            "serial_number": self.serial,
    }

    @property
    def unique_id(self):
        return f"{self.serial}_{self._attr_name.lower().replace(' ', '_')}"

    @property
    def is_on(self):
        try:
            val = self.coordinator.data[self._register]
            return not bool(val) if self._invert else bool(val)
        except Exception:
            return False

    async def async_turn_on(self, **kwargs):
        value = self._write_off if self._invert else self._write_on
        client = self.coordinator.client
        unit_id = self.coordinator.unit_id
        await self.hass.async_add_executor_job(client.write_register, self._register, value, unit_id)

    async def async_turn_off(self, **kwargs):
        value = self._write_on if self._invert else self._write_off
        client = self.coordinator.client
        unit_id = self.coordinator.unit_id
        await self.hass.async_add_executor_job(client.write_register, self._register, value, unit_id)