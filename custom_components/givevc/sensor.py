from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .helpers import decode_float, decode_unsigned_32


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")

    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusSensorEntity(coordinator, config, serial, entry)
        for config in register_map
        if config["type"] == "sensor"
    ]
    # Add timestamp entities (type == "timestamp")
    entities += [
        ModbusTimestampEntity(coordinator, config, serial, entry)
        for config in register_map
        if config.get("type") == "timestamp"
    ]
    async_add_entities(entities)


class ModbusSensorEntity(SensorEntity):
    def __init__(self, coordinator, config, serial, config_entry: ConfigEntry | None = None):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config["name"]
        self._config_entry = config_entry
        self._register = config["register"]
        self._scale = config.get("scale", 1.0)
        self._unit = config.get("unit", "")
        self._float = config.get("float", False)
        self._byte_order = config.get("byte_order", None)
        self._device_class = config.get("device_class")
        self._lookup = config.get("lookup")
        # stable unique id used by entity registry
        self._attr_unique_id = f"givevc_{serial}_{slugify(self._attr_name)}"

        # optionally show device-based names
        # self._attr_has_entity_name = True

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
        return self._attr_unique_id

    async def async_added_to_hass(self) -> None:
        """Register suggested object id in entity registry so entity_id includes the serial."""
        await super().async_added_to_hass()

        registry = er.async_get(self.hass)
        suggested_object_id = DOMAIN+f"_{self.serial}_{slugify(self._attr_name)}"
        registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=self._attr_unique_id,
            suggested_object_id=suggested_object_id,
            config_entry=self._config_entry,
        )

    @property
    def native_unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class
    @property
    def native_value(self):
        try:
            data = self.coordinator.data
            if self._float:
                val = decode_float(
                    data[self._register : self._register + 2], self._byte_order
                )
            elif self._byte_order:
                # default assumption: two consecutive registers form an unsigned 32-bit value
                val = decode_unsigned_32(
                    data[self._register : self._register + 2], self._byte_order
                )
            else:
                val = data[self._register]

            # If a lookup mapping is provided, map the raw (unscaled) value to a state
            if self._lookup:
                try:
                    key = str(int(val)) if isinstance(val, (int, float)) else str(val)
                except (TypeError, ValueError):
                    key = str(val)
                mapped = self._lookup.get(key)
                if mapped is not None:
                    return mapped

            return round(val * self._scale, 2)
        except (IndexError, TypeError, KeyError):
            return None


class ModbusTimestampEntity(SensorEntity):
    """Timestamp sensor built from three registers: hour, minute, second."""

    def __init__(self, coordinator, config, serial, config_entry: ConfigEntry | None = None):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config.get("name")
        self._config_entry = config_entry
        self._register = config.get("register")
        self._register_minute = config.get("register_minute")
        self._register_second = config.get("register_second")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_unique_id = f"givevc_{serial}_{slugify(self._attr_name)}_timestamp"

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
        return self._attr_unique_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        registry = er.async_get(self.hass)
        suggested_object_id = f"givvc_{self.serial}_{slugify(self._attr_name)}_ts"
        registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=self._attr_unique_id,
            suggested_object_id=suggested_object_id,
            config_entry=self._config_entry,
        )

    @property
    def native_value(self):
        try:
            data = self.coordinator.data
            hour = int(data[self._register])
            minute = int(data[self._register_minute]) if self._register_minute is not None else 0
            second = int(data[self._register_second]) if self._register_second is not None else 0

            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return None

            tz = dt_util.DEFAULT_TIME_ZONE
            now_local = dt_util.now().astimezone(tz)
            dt_val = datetime(
                year=now_local.year,
                month=now_local.month,
                day=now_local.day,
                hour=hour,
                minute=minute,
                second=second,
                tzinfo=tz,
            )
            return dt_val
        except (IndexError, TypeError, KeyError):
            return None
