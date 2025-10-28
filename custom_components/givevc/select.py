from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
import os
import json

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")
    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusSelectEntity(coordinator, config, serial)
        for config in register_map if config["type"] == "select"
    ]
    async_add_entities(entities)


class ModbusSelectEntity(SelectEntity):
    def __init__(self, coordinator, config, serial):
        self.coordinator = coordinator
        self.serial= serial
        self._attr_name = config["name"]
        self._register = config["register"]
        self._mode = config.get("mode", "holding")

        # Load lookup table from inline or external file
        if "lookup_file" in config:
            lookup_path = os.path.join(os.path.dirname(__file__), config["lookup_file"])
            with open(lookup_path) as f:
                self._lookup = {int(k): v for k, v in json.load(f).items()}
        else:
            self._lookup = {int(k): v for k, v in config.get("lookup", {}).items()}

        self._reverse_lookup = {v: k for k, v in self._lookup.items()}
        self._options = list(self._reverse_lookup.keys())
        self._current_option = None

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
    def options(self):
        return self._options

    @property
    def current_option(self):
        try:
            raw = self.coordinator.data[self._register]
            return self._lookup.get(raw)
        except Exception:
            return None

    async def async_select_option(self, option: str):
        value = self._reverse_lookup.get(option)
        if value is None:
            return

        client = self.coordinator.client
        unit_id = self.coordinator.unit_id

        if self._mode == "coil":
            await self.hass.async_add_executor_job(client.write_coil, self._register, value, unit_id)
        else:
            await self.hass.async_add_executor_job(client.write_register, self._register, value, unit_id)

        self._current_option = option