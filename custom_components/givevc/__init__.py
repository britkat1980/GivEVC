from .const import DOMAIN
from .coordinator import ModbusCoordinator
from homeassistant.core import HomeAssistant
import json
from pathlib import Path
import logging

_LOGGER = logging.getLogger(__name__)

def get_map():
    # Try to load register_map.json from the integration directory and merge
    # into the entry data. This allows users to change the file and have the
    # integration pick up changes on Home Assistant restart.
    try:
        reg_file = Path(__file__).parent / "register_map.json"
        if reg_file.exists():
            with reg_file.open() as f:
                reg_map = json.load(f)
            return reg_map
        else:
            return []
    except Exception:
        _LOGGER.debug("Failed loading register_map.json; continuing without it")

async def async_unload_entry(hass, entry):
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        coordinator.shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "number", "switch", "select"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup_entry(hass, entry):
    """Set up the integration from a config entry.

    Load a local register_map.json (if present) and update the config entry
    data so platforms pick up the latest network map without re-running the
    config flow.
    """
    hass.data.setdefault(DOMAIN, {})
    config = dict(entry.data)
    try:
        # Normalize register fields (strings to ints where appropriate)
        reg_map = await hass.async_add_executor_job(get_map)
        parsed_map = []
        for cfg in reg_map:
            cfg_copy = dict(cfg)
            reg_raw = cfg_copy.get("register")
            try:
                if isinstance(reg_raw, str):
                    cfg_copy["register"] = int(reg_raw, 0)
            except Exception:
                _LOGGER.debug("Invalid register value in map: %s", reg_raw)
            parsed_map.append(cfg_copy)
        config["register_map"] = parsed_map
        # Update the config entry so platforms see the map
        hass.config_entries.async_update_entry(entry, data=config)
    except Exception:
        _LOGGER.debug("Failed processing register_map.json; continuing without it")
    coordinator = ModbusCoordinator(
        hass,
        host=config["host"],
        port=502,
        unit_id=1,
        scan_interval=config["scan_interval"],
        register_count=60,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in ["sensor", "number", "switch", "select"]:
        hass.async_create_task(hass.config_entries._async_forward_entry_setup(entry, platform,False))
    return True