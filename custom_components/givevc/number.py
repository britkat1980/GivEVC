import struct

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helpers import decode_float, decode_signed_16, decode_signed_32


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data.get("serial")
    register_map = entry.data.get("register_map", [])

    entities = [
        ModbusNumberEntity(coordinator, config, serial)
        for config in register_map
        if config["type"] == "number"
    ]
    async_add_entities(entities)


class ModbusNumberEntity(NumberEntity):
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
        self._min = config.get("min", 0)
        self._max = config.get("max", 100)
        self._step = config.get("step", 1)
        self._value = None
        self._mode = config.get("mode", "auto")  # default to auto if not specified

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"givevc_{self.serial}")},
            "name": "GivEVC",
            "manufacturer": "GivEnergy",
            "model": "GivEVC",
        }

    @property
    def mode(self):
        return self._mode

    @property
    def unique_id(self):
        return f"{self.serial}_{self._attr_name.lower().replace(' ', '_')}"

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
                val = decode_float(
                    data[self._register : self._register + 2], self._byte_order
                )
            elif self._signed and self._register + 1 < len(data):
                val = decode_signed_32(
                    data[self._register : self._register + 2], self._byte_order
                )
            elif self._signed:
                val = decode_signed_16(data[self._register])
            else:
                val = data[self._register]
            return round(val * self._scale, 2)
        except Exception:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value on the device (native units)."""
        scaled = int(value / self._scale)
        client = self.coordinator.client
        unit_id = self.coordinator.unit_id

        if self._float:
            raw = struct.pack(">f", value)
            if self._byte_order == "DCBA":
                raw = raw[::-1]
            elif self._byte_order == "BADC":
                raw = raw[1:2] + raw[0:1] + raw[3:4] + raw[2:3]
            elif self._byte_order == "CDAB":
                raw = raw[2:4] + raw[0:2]
            regs = struct.unpack(">HH", raw)
            await self.hass.async_add_executor_job(
                lambda: client.write_registers(self._register, regs, unit=unit_id)
            )
        elif self._signed and self._register + 1 < len(self.coordinator.data):
            raw = struct.pack(">i", scaled)
            regs = struct.unpack(">HH", raw)
            await self.hass.async_add_executor_job(
                lambda: client.write_registers(self._register, regs, unit=unit_id)
            )
        else:
            await self.hass.async_add_executor_job(
                lambda: client.write_register(self._register, scaled, unit=unit_id)
            )

        # Update local cached value and request a coordinator refresh
        self._value = value
        await self.coordinator.async_request_refresh()
