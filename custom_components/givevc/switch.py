from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify
from homeassistant.helpers import entity_registry as er

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
        self._attr_default_entity_id = f"givevc_{serial}_{slugify(self._attr_name)}"
        self._attr_unique_id = f"givevc_{serial}_{slugify(self._attr_name)}"
        self._register = config["register"]
        self._mode = config.get("mode", "holding")
        self._invert = config.get("invert", False)
        self._write_on = config.get("write_on", 1)
        self._write_off = config.get("write_off", 0)

    @property
    def device_info(self):
        return {
            "identifiers": {(f"givevc_{self.serial}")},
            "name": "GivEVC",
            "manufacturer": "GivEnergy",
            "model": "GivEVC",
            "serial_number": self.serial,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        registry = er.async_get(self.hass)
        #suggested_object_id = f"givvc_{self.serial}_{slugify(self._attr_name)}"
        registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=self._attr_default_entity_id,
            suggested_object_id=self._attr_default_entity_id,
            config_entry=self._config_entry,
        )


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

    async def async_update(self):
        await self.coordinator.async_request_refresh()