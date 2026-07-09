"""Shared building blocks for Simple Smart Cover entities.

Every entity created by the integration belongs to the same device (one cover
group) and most of them either mirror attributes of the virtual cover entity
or react to its state changes. The mixins and helper functions here remove the
boilerplate that was previously duplicated across the sensor and button
modules.
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .const import DOMAIN

# Interval at which pause sensors refresh so the remaining-minutes value counts
# down and the binary sensor turns off once the pause expires.
PAUSE_REFRESH_INTERVAL = timedelta(minutes=1)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def build_device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Return DeviceInfo so HA groups all entities under one cover group device."""
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=config_entry.title,
        manufacturer="Simple Smart Cover",
        model="Cover Group",
    )


def get_cover_entity(hass: HomeAssistant, entry_id: str):
    """Return the virtual SimpleSmartCoverEntity for a config entry, or None."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
    if entry_data is None:
        return None
    return entry_data.get("cover")


def get_cover_entity_id(hass: HomeAssistant, entry_id: str, title: str) -> str:
    """Return the virtual cover entity_id.

    Primary lookup is the entity registry by unique_id, with a slugified-title
    fallback for edge cases where the registry is not yet populated.
    """
    entity_registry = er.async_get(hass)
    cover_entity_id = entity_registry.async_get_entity_id(
        "cover", DOMAIN, f"{entry_id}_cover"
    )
    if cover_entity_id is None:
        cover_entity_id = f"cover.{title.lower().replace(' ', '_')}"
    return cover_entity_id


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class SimpleSmartCoverDeviceMixin:
    """Provide device_info and cover entity lookup for group entities.

    Subclasses must set `self.hass`, `self._config_entry` and `self._entry_id`
    (typically in __init__) before using these members.
    """

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info linking this entity to its cover group."""
        return build_device_info(self._config_entry)

    def _get_cover_entity(self):
        """Return the virtual cover entity for this config entry, or None."""
        return get_cover_entity(self.hass, self._entry_id)


class SimpleSmartCoverStateSensorMixin(SimpleSmartCoverDeviceMixin):
    """Base for sensors that mirror attributes of the virtual cover entity.

    Subclasses implement `_update_from_cover_state(state)` to extract their
    value (and optional extra attributes) from a cover state object.
    """

    _cover_entity_id: str | None = None

    def _update_from_cover_state(self, state) -> None:
        """Update the sensor value from a cover state object.

        Called once with the current state on startup and again on every
        cover state change. Subclasses must override this.
        """
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Register the cover state-change listener and seed the initial value."""
        await super().async_added_to_hass()

        self._cover_entity_id = get_cover_entity_id(
            self.hass, self._entry_id, self._config_entry.title
        )
        self._update_from_cover_state(self.hass.states.get(self._cover_entity_id))

        @callback
        def _async_state_changed(event) -> None:
            """Forward cover state changes to the sensor."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            self._update_from_cover_state(new_state)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._cover_entity_id, _async_state_changed
            )
        )


class SimpleSmartCoverPauseEntityMixin(SimpleSmartCoverDeviceMixin):
    """Base for the pause binary sensor and remaining-minutes sensor.

    Both sensors read their value live from the cover entity and only need a
    state listener plus a periodic refresh so the value counts down / clears
    when the pause expires.
    """

    async def async_added_to_hass(self) -> None:
        """Register state listener, periodic refresh and emit an initial state."""
        await super().async_added_to_hass()

        cover_entity_id = get_cover_entity_id(
            self.hass, self._entry_id, self._config_entry.title
        )

        @callback
        def _async_state_changed(event) -> None:
            """Refresh when the virtual cover entity changes state."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, cover_entity_id, _async_state_changed
            )
        )

        @callback
        def _async_periodic_update(now) -> None:
            """Periodically refresh so expired pauses are cleared promptly."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_interval(
                self.hass, _async_periodic_update, PAUSE_REFRESH_INTERVAL
            )
        )

        self.async_write_ha_state()
