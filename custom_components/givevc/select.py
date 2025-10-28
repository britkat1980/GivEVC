import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")
    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusSelectEntity(coordinator, config, serial)
        for config in register_map
        if config["type"] == "select"
    ]
    async_add_entities(entities)


class ModbusSelectEntity(SelectEntity):
    def __init__(self, coordinator, config, serial):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config["name"]
        self._register = config["register"]


        # Prefer lookup provided in the config (populated at setup).
        # Lookup files should be resolved at startup (async_setup_entry) and
        # included in the `register_map` entries so platforms don't perform
        # file I/O at runtime.
        raw_lookup = config.get("lookup")
        if not raw_lookup:
            _LOGGER.debug(
                "No lookup provided for select '%s' (register %s); defaulting to empty mapping",
                self._attr_name,
                self._register,
            )
            raw_lookup = {}

        # Ensure keys are ints and values preserved
        try:
            self._lookup = {int(k): v for k, v in raw_lookup.items()}
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to parse lookup for %s: %s", self._attr_name, err)
            self._lookup = {}

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
            "serial_number": self.serial,
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
        try:
            value = self._reverse_lookup.get(option)
            if value is None:
                return

            client = self.coordinator.client

            await self.hass.async_add_executor_job(
                    lambda: client.write_registers(self._register, [value])
                )
            self._current_option = option
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to set option '%s' for %s: %s", option, self._attr_name, err)