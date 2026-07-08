"""Trigger handling for Simple Smart Cover integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
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
                cover_entity.set_evening_state(False)
                hass.async_create_task(cover_entity.async_update_position())

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
            hass.async_create_task(cover_entity.async_update_position())

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

    # Sunset trigger: schedule at the actual next_setting time.
    # Using sun.sun's "rising" attribute is not reliable because it is False
    # for the whole afternoon, causing premature evening activation.
    if data.get(CONF_ENABLE_EVENING, True):
        sunset_remove = [None]

        @callback
        def _sunset_trigger(now):
            cover_entity.set_evening_state(True)
            hass.async_create_task(cover_entity.async_update_position())
            _schedule_next_sunset()

        @callback
        def _schedule_next_sunset():
            sun_state = hass.states.get("sun.sun")
            if sun_state is None:
                return
            next_setting = sun_state.attributes.get("next_setting")
            if next_setting is None:
                return
            if isinstance(next_setting, str):
                next_setting = dt_util.parse_datetime(next_setting)
            if next_setting is None:
                return
            next_setting = dt_util.as_utc(next_setting)
            if next_setting < dt_util.utcnow():
                return
            if sunset_remove[0] is not None:
                sunset_remove[0]()
            sunset_remove[0] = async_track_point_in_utc_time(
                hass, _sunset_trigger, next_setting
            )

        _schedule_next_sunset()
        remove_callbacks.append(
            lambda: sunset_remove[0]() if sunset_remove[0] is not None else None
        )

    # Store remove callbacks on the entry
    hass.data.setdefault("simple_smart_cover_triggers", {})
    hass.data["simple_smart_cover_triggers"][entry.entry_id] = remove_callbacks
