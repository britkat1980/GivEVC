import logging

from pymodbus.client import AsyncModbusTcpClient

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")
    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusSelectEntity(coordinator, config, serial, entry)
        for config in register_map
        if config["type"] == "select"
    ]
    async_add_entities(entities)


class ModbusSelectEntity(SelectEntity):
    def __init__(self, coordinator, config, serial, config_entry: ConfigEntry | None = None):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config["name"]
        self._register = config["register"]
        self._attr_default_entity_id = f"givevc_{serial}_{slugify(self._attr_name)}"
        self._attr_unique_id = f"givevc_{serial}_{slugify(self._attr_name)}"
        self._config_entry = config_entry

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
            "identifiers": {(f"givevc_{self.serial}")},
            "name": "GivEVC",
            "manufacturer": "GivEnergy",
            "model": "GivEVC",
            "serial_number": self.serial,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        registry = er.async_get(self.hass)
        suggested_object_id = f"givvc_{self.serial}_{slugify(self._attr_name)}"
        registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=self._attr_default_entity_id,
            suggested_object_id=suggested_object_id,
            config_entry=self._config_entry,
        )


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
            async with AsyncModbusTcpClient(host=self.coordinator.host, port=502) as client:
                if not client.connected:
                    raise ConnectionError("Modbus client failed to connect")
                success = await client.write_registers(self._register, [value])
            if success:
                await self.coordinator.async_request_refresh()
            self._current_option = option
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to set option '%s' for %s: %s", option, self._attr_name, err)

    async def async_update(self):
        await self.coordinator.async_request_refresh()