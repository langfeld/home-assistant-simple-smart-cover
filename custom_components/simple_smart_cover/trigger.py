"""Trigger handling for Simple Smart Cover integration.

Three trigger types drive re-evaluation of the cover position:
- A daily morning trigger that clears evening mode and re-evaluates.
- A periodic re-evaluation interval (15/30/60 minutes).
- A sunset trigger that enables evening mode, re-scheduled every day.

The sunset trigger reads ``next_setting`` from sun.sun and re-schedules itself
after firing, because the sun entity's ``rising`` attribute is False for the
entire afternoon and cannot be used to detect sunset reliably.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_point_in_utc_time,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_EVENING,
    CONF_ENABLE_MORNING,
    CONF_ENABLE_REEVALUATION,
    CONF_MORNING_TIME,
    CONF_REEVALUATE_INTERVAL,
    DOMAIN,
    REEVALUATE_INTERVAL_TRACKING,
)
from .cover import SimpleSmartCoverEntity

_LOGGER = logging.getLogger(__name__)

# If sun.sun is not yet available, retry sunset scheduling at this interval.
_SUNSET_RETRY_INTERVAL = timedelta(minutes=5)


async def async_setup_triggers(
    hass: HomeAssistant, entry: ConfigEntry, cover_entity: SimpleSmartCoverEntity
) -> None:
    """Set up time and sun triggers for the cover entity."""
    data = {**entry.data, **entry.options}
    remove_callbacks: list = []

    # -- Morning trigger: clear evening mode and re-evaluate -----------------
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

    # -- Re-evaluation interval ----------------------------------------------
    if data.get(CONF_ENABLE_REEVALUATION, True):
        interval = data.get(CONF_REEVALUATE_INTERVAL, "30")
        tracking_kwargs = REEVALUATE_INTERVAL_TRACKING.get(interval)

        if tracking_kwargs is not None:

            @callback
            def _reevaluate_trigger(now):
                hass.async_create_task(cover_entity.async_update_position())

            remove_callbacks.append(
                async_track_time_change(hass, _reevaluate_trigger, **tracking_kwargs)
            )

    # -- Sunset trigger: enable evening mode, then re-schedule ---------------
    if data.get(CONF_ENABLE_EVENING, True):
        sunset_remove: list = [None]

        @callback
        def _sunset_trigger(now):
            """Enable evening mode and schedule the next sunset."""
            cover_entity.set_evening_state(True)
            hass.async_create_task(cover_entity.async_update_position())
            _schedule_next_sunset()

        @callback
        def _schedule_next_sunset():
            """Schedule the next sunset trigger from sun.sun's next_setting."""
            sun_state = hass.states.get("sun.sun")
            if sun_state is None:
                _LOGGER.warning(
                    "sun.sun not available, retrying sunset scheduling in %s minutes",
                    _SUNSET_RETRY_INTERVAL.total_seconds() / 60,
                )
                if sunset_remove[0] is not None:
                    sunset_remove[0]()
                sunset_remove[0] = async_track_point_in_utc_time(
                    hass, _sunset_retry, dt_util.utcnow() + _SUNSET_RETRY_INTERVAL
                )
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

        @callback
        def _sunset_retry(now):
            """Retry scheduling after sun.sun was unavailable."""
            _schedule_next_sunset()

        _schedule_next_sunset()
        remove_callbacks.append(
            lambda: sunset_remove[0]() if sunset_remove[0] is not None else None
        )

    # Store remove callbacks on the entry so they are cleaned up on unload.
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    hass.data[DOMAIN][entry.entry_id]["trigger_removals"] = remove_callbacks
