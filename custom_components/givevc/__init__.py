from .const import DOMAIN
from .coordinator import ModbusCoordinator
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    config = entry.data

    coordinator = ModbusCoordinator(
        hass,
        host=config["host"],
        port=502,
        unit_id=1,
        scan_interval=config["scan_interval"],
        register_count=60
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in ["sensor", "number", "switch", "select"]:
        hass.async_create_task(hass.config_entries._async_forward_entry_setup(entry, platform,False))

    return True