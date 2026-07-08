"""The Simple Smart Cover integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .trigger import async_setup_triggers

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.COVER, Platform.SENSOR]


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
        # Prefer the live cover entity stored during platform setup.
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        cover_entity = entry_data.get("cover") if entry_data else None

        if cover_entity is None:
            # Fallback: look up the entity via the entity registry by unique_id.
            entity_registry = er.async_get(hass)
            cover_entity_id = entity_registry.async_get_entity_id(
                "cover", DOMAIN, f"{entry.entry_id}_cover"
            )
            if cover_entity_id:
                cover_component = hass.data.get("entity_components", {}).get("cover")
                if cover_component:
                    cover_entity = cover_component.get_entity(cover_entity_id)

        if cover_entity:
            await async_setup_triggers(hass, entry, cover_entity)
        else:
            _LOGGER.error(
                "Could not find cover entity for %s; interval/evening triggers will not run",
                entry.title,
            )

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
