"""Trigger handling for Simple Smart Cover integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_point_in_utc_time,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_MORNING,
    CONF_ENABLE_EVENING,
    CONF_ENABLE_REEVALUATION,
    CONF_MORNING_TIME,
    CONF_REEVALUATE_INTERVAL,
)
from .cover import SimpleSmartCoverEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_triggers(
    hass: HomeAssistant, entry: ConfigEntry, cover_entity: SimpleSmartCoverEntity
) -> None:
    """Set up time and sun triggers for the cover entity."""
    data = entry.data
    remove_callbacks = []

    # Morning time trigger
    if data.get(CONF_ENABLE_MORNING, True):
        morning_time = data.get(CONF_MORNING_TIME, "07:00:00")
        try:
            hour, minute, second = map(int, morning_time.split(":"))

            @callback
            def _morning_trigger(now):
                hass.async_create_task(cover_entity.async_update_position(is_evening=False))

            remove_callbacks.append(
                async_track_time_change(
                    hass, _morning_trigger, hour=hour, minute=minute, second=second
                )
            )
        except (ValueError, AttributeError):
            _LOGGER.error("Invalid morning time format: %s", morning_time)

    # Reevaluation interval triggers
    if data.get(CONF_ENABLE_REEVALUATION, True):
        interval = data.get(CONF_REEVALUATE_INTERVAL, "30")

        @callback
        def _reevaluate_trigger(now):
            hass.async_create_task(cover_entity.async_update_position(is_evening=False))

        if interval == "15":
            remove_callbacks.append(
                async_track_time_change(hass, _reevaluate_trigger, minute="/15")
            )
        elif interval == "30":
            remove_callbacks.append(
                async_track_time_change(hass, _reevaluate_trigger, minute="/30")
            )
        elif interval == "60":
            remove_callbacks.append(
                async_track_time_change(hass, _reevaluate_trigger, minute="0")
            )

    # Sunset trigger
    if data.get(CONF_ENABLE_EVENING, True):

        @callback
        def _sun_event(event):
            if event.data.get("new_state") is None:
                return
            new_state = event.data["new_state"]
            rising = new_state.attributes.get("rising")
            # rising=False means sun is setting
            if rising is False:
                hass.async_create_task(cover_entity.async_update_position(is_evening=True))

        remove_callbacks.append(
            async_track_state_change_event(hass, "sun.sun", _sun_event)
        )

    # Store remove callbacks on the entry
    hass.data.setdefault("simple_smart_cover_triggers", {})
    hass.data["simple_smart_cover_triggers"][entry.entry_id] = remove_callbacks
