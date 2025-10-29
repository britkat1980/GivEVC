import struct

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pymodbus.client import AsyncModbusTcpClient
from homeassistant.util import slugify
from homeassistant.helpers import entity_registry as er


from .const import DOMAIN
from .helpers import decode_float, decode_unsigned_32


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")
    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusNumberEntity(coordinator, config, serial, entry)
        for config in register_map
        if config["type"] == "number"
    ]
    async_add_entities(entities)


class ModbusNumberEntity(NumberEntity):
    def __init__(self, coordinator, config, serial, config_entry: ConfigEntry | None = None):
        self.coordinator = coordinator
        self.serial = serial
        self._attr_name = config["name"]
        self._attr_default_entity_id = f"givevc_{serial}_{slugify(self._attr_name)}"
        self._attr_unique_id = f"givevc_{serial}_{slugify(self._attr_name)}"
        self._register = config["register"]
        self._config_entry = config_entry
        self._scale = config.get("scale", 1.0)
        self._unit = config.get("unit", "")
        self._float = config.get("float", False)
        self._byte_order = config.get("byte_order", None)
        self._min = config.get("min", 0)
        self._max = config.get("max", 100)
        self._step = config.get("step", 1)
        self._value = None
        self._mode = config.get("mode", "auto")  # default to auto if not specified

    @property
    def device_info(self):
        return {
            "identifiers": {(f"givevc_{self.serial}")},
            "name": "GivEVC",
            "manufacturer": "GivEnergy",
            "model": "GivEVC",
            "serial_number": self.serial,
        }

    @property
    def mode(self):
        return self._mode

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
    def native_unit_of_measurement(self):
        return self._unit

    @property
    def native_min_value(self):
        return self._min

    @property
    def native_max_value(self):
        return self._max

    @property
    def native_step(self):
        return self._step

    @property
    def native_value(self):
        """Return the current value from the coordinator data in native units."""
        try:
            data = self.coordinator.data
            if self._float:
                val = decode_float(data[self._register:self._register+2], self._byte_order)
            elif self._byte_order:
                # default assumption: two consecutive registers form an unsigned 32-bit value
                val = decode_unsigned_32(data[self._register:self._register+2], self._byte_order)
            else:
                val = data[self._register]
            return round(val * self._scale, 2)
        except Exception:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value on the device (native units)."""
        try:
            scaled = round(value / self._scale)
            #client = self.coordinator.client
            async with AsyncModbusTcpClient(host=self.coordinator.host, port=502) as client:
                if not client.connected:
                    raise ConnectionError("Modbus client failed to connect")
                if self._float:
                    raw = struct.pack(">f", value)
                    if self._byte_order == "DCBA":
                        raw = raw[::-1]
                    elif self._byte_order == "BADC":
                        raw = raw[1:2] + raw[0:1] + raw[3:4] + raw[2:3]
                    elif self._byte_order == "CDAB":
                        raw = raw[2:4] + raw[0:2]
                    regs = struct.unpack(">HH", raw)
                    success = await client.write_registers(self._register, regs)

                elif self._byte_order:
                    raw = struct.pack(">i", scaled)
                    regs = struct.unpack(">HH", raw)

                    success = await client.write_registers(self._register, regs)
                else:
                    success = await client.write_registers(self._register, [scaled])
            self._value = value
            if success:
                await self.coordinator.async_request_refresh()

        except Exception:
            return None

    async def async_update(self):
        await self.coordinator.async_request_refresh()