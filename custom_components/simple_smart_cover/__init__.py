"""The Simple Smart Cover integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .trigger import async_setup_triggers

PLATFORMS = [Platform.COVER, Platform.SENSOR]


def is_valid_time(value: str) -> bool:
    """Validate time string HH:MM:SS."""
    try:
        parts = value.split(":")
        if len(parts) != 3:
            return False
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59
    except (ValueError, AttributeError):
        return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Simple Smart Cover from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Migrate old config keys to new names
    data = dict(entry.data)
    migration_map = {
        "sunny_in_angle": "position_sunny_in_angle",
        "sunny_outside_angle": "position_sunny_outside_angle",
        "cloudy": "position_cloudy",
        "evening": "position_evening",
    }
    needs_update = False
    for old_key, new_key in migration_map.items():
        if old_key in data and new_key not in data:
            data[new_key] = data.pop(old_key)
            needs_update = True
    if needs_update:
        hass.config_entries.async_update_entry(entry, data=data)

    hass.data[DOMAIN][entry.entry_id] = {
        "config_entry": entry,
        "cover": None,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup triggers after platforms are loaded
    async def _setup_triggers(_):
        cover_entity_id = f"cover.{entry.data['name'].lower().replace(' ', '_')}"
        cover_entity = hass.data.get("entity_components", {}).get("cover", {}).get_entity(cover_entity_id)
        if cover_entity:
            await async_setup_triggers(hass, entry, cover_entity)

    entry.async_on_unload(
        hass.bus.async_listen_once("homeassistant_started", _setup_triggers)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        trigger_removals = hass.data.get("simple_smart_cover_triggers", {}).pop(entry.entry_id, [])
        for remove_callback in trigger_removals:
            remove_callback()

    return unload_ok
