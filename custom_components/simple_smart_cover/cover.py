"""Cover platform for Simple Smart Cover integration."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_COVERS,
    CONF_WEATHER_ENTITY,
    CONF_MORNING_TIME,
    CONF_ENABLE_MORNING,
    CONF_ENABLE_EVENING,
    CONF_WINDOW_ORIENTATION,
    CONF_SUN_ANGLE_TOLERANCE,
    CONF_MIN_SUN_ELEVATION,
    CONF_TEMP_THRESHOLD,
    CONF_TEMP_SOURCE,
    CONF_USE_FORECAST_MAX_TEMP,
    CONF_TEMP_FORECAST_ENTITY,
    CONF_CLOUDY_CONDITIONS,
    CONF_POSITION_SUNNY_IN_ANGLE,
    CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
    CONF_POSITION_CLOUDY,
    CONF_POSITION_EVENING,
    CONF_INVERT_POSITIONS,
    CONF_ENABLE_QUIET_MODE,
    CONF_QUIET_START,
    CONF_QUIET_END,
    CONF_ENABLE_REEVALUATION,
    CONF_REEVALUATE_INTERVAL,
    CONF_MIN_POSITION_CHANGE,
    CONF_ENABLE_MANUAL_ACTIVITY_PAUSE,
    CONF_MANUAL_ACTIVITY_DURATION,
    CONF_TEST_MODE,
    DEFAULT_POSITION_SUNNY_IN_ANGLE,
    DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
    DEFAULT_POSITION_CLOUDY,
    DEFAULT_POSITION_EVENING,
    DEFAULT_MANUAL_ACTIVITY_DURATION,
    DEFAULT_WINDOW_ORIENTATION,
    DEFAULT_SUN_ANGLE_TOLERANCE,
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_CLOUDY_CONDITIONS,
    DEFAULT_MIN_POSITION_CHANGE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simple Smart Cover cover entity."""
    data = config_entry.data

    async_add_entities(
        [
            SimpleSmartCoverEntity(
                hass=hass,
                config_entry=config_entry,
                name=data[CONF_NAME],
            )
        ]
    )


class SimpleSmartCoverEntity(CoverEntity):
    """Representation of a Simple Smart Cover group."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the cover entity."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_cover"

        self._target_position = 100
        self._decision_reason = "unknown"
        self._should_move = False
        self._last_sent_positions: dict[str, tuple[datetime, int]] = {}
        self._manual_pause_until: datetime | None = None
        self._force_evening = False
        self._startup_time = dt_util.now()

    @property
    def _data(self) -> dict[str, Any]:
        """Return merged config entry data and options."""
        return {**self._config_entry.data, **self._config_entry.options}

    async def async_added_to_hass(self) -> None:
        """Register update listener and cover state listeners."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN][self._entry_id]["cover"] = self
        self.async_on_remove(
            self._config_entry.add_update_listener(self._async_update_options)
        )

        # Listen to real cover state changes to detect manual/external moves.
        covers = self._data.get(CONF_COVERS, [])
        if covers:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, covers, self._async_cover_state_changed
                )
            )

    async def _async_update_options(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        await self.async_update_position()

    @callback
    def _async_cover_state_changed(self, event) -> None:
        """Detect manual or external cover movements."""
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            return

        new_state = event.data.get("new_state")
        if new_state is None:
            return

        now = dt_util.now()
        # Ignore state changes shortly after startup to avoid false positives
        # while HA is still restoring states.
        if now < self._startup_time + timedelta(seconds=60):
            return

        entity_id = new_state.entity_id
        grace_period = timedelta(seconds=120)
        position_tolerance = 3  # percent

        last_sent = self._last_sent_positions.get(entity_id)
        if last_sent is not None:
            sent_time, sent_pos = last_sent
            if now < sent_time + grace_period:
                # Movement shortly after our own command: assume it is ours.
                return
            try:
                current_pos = int(new_state.attributes.get("current_position", -1))
                if current_pos >= 0 and abs(current_pos - sent_pos) <= position_tolerance:
                    # Position matches what we requested: not a manual move.
                    return
            except (ValueError, TypeError):
                pass

        # Movement was not initiated by us: start manual activity pause.
        duration_minutes = self._data.get(
            CONF_MANUAL_ACTIVITY_DURATION, DEFAULT_MANUAL_ACTIVITY_DURATION
        )
        self._manual_pause_until = now + timedelta(minutes=duration_minutes)
        _LOGGER.debug(
            "Manual activity detected on %s, pausing automation until %s",
            entity_id,
            self._manual_pause_until,
        )

    def set_evening_state(self, is_evening: bool) -> None:
        """Set whether evening mode should be forced."""
        self._force_evening = is_evening

    @property
    def current_cover_position(self) -> int:
        """Return current cover position."""
        return self._target_position

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "decision_reason": self._decision_reason,
            "should_move": self._should_move,
            "target_position": self._target_position,
        }

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._target_position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        position = kwargs.get("position", 100)
        self._target_position = int(position)
        self.async_write_ha_state()

    def _get_state_float(self, entity_id: str) -> float:
        """Get a state value as float."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0

    def _get_state_attr_float(self, entity_id: str, attribute: str) -> float:
        """Get a state attribute as float."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return 0.0
        value = state.attributes.get(attribute)
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _is_quiet_time(self) -> bool:
        """Check if current time is in quiet mode range."""
        if not self._data.get(CONF_ENABLE_QUIET_MODE, False):
            return False

        now = dt_util.now()
        now_str = now.strftime("%H:%M:%S")
        quiet_start = self._data.get(CONF_QUIET_START, "22:00:00")
        quiet_end = self._data.get(CONF_QUIET_END, "07:00:00")

        if quiet_start <= quiet_end:
            return quiet_start <= now_str <= quiet_end
        return now_str >= quiet_start or now_str <= quiet_end

    def is_manual_pause_active(self) -> bool:
        """Return whether manual activity pause is currently active."""
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            return False
        if self._manual_pause_until is None:
            return False
        return dt_util.now() < self._manual_pause_until

    def get_pause_remaining_minutes(self) -> int | None:
        """Return remaining pause minutes, or None if not paused."""
        if not self.is_manual_pause_active():
            return None
        remaining = self._manual_pause_until - dt_util.now()
        return max(0, int(remaining.total_seconds() // 60))

    def reset_manual_pause(self) -> None:
        """Reset the manual activity pause immediately."""
        self._manual_pause_until = None
        _LOGGER.debug("Manual activity pause reset for %s", self._attr_name)
        self.async_write_ha_state()

    def update_pause_state(self) -> None:
        """Refresh manual activity pause state. Call when cover states change."""
        self._manual_activity_detected()

    def _manual_activity_detected(self) -> bool:
        """Return whether manual activity pause is currently active."""
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            self._manual_pause_until = None
            return False

        if self._manual_pause_until is None:
            return False

        if dt_util.now() < self._manual_pause_until:
            return True

        self._manual_pause_until = None
        return False

    def _get_temperature(self) -> float:
        """Get the temperature to use for decision making."""
        weather_entity = self._data[CONF_WEATHER_ENTITY]
        fallback = self._get_state_attr_float(weather_entity, "temperature")

        if self._data.get(CONF_USE_FORECAST_MAX_TEMP, False):
            forecast_entities = self._data.get(CONF_TEMP_FORECAST_ENTITY)
            if forecast_entities:
                forecast_entity = (
                    forecast_entities[0]
                    if isinstance(forecast_entities, list)
                    else forecast_entities
                )
                return self._get_state_float(forecast_entity) or fallback

        temp_sources = self._data.get(CONF_TEMP_SOURCE)
        if temp_sources:
            temp_source = (
                temp_sources[0] if isinstance(temp_sources, list) else temp_sources
            )
            return self._get_state_float(temp_source) or fallback

        return fallback

    def _calculate_target_position(self, is_evening: bool = False) -> int:
        """Calculate the target cover position."""
        if is_evening:
            position = self._data.get(CONF_POSITION_EVENING, DEFAULT_POSITION_EVENING)
            return 100 - position if self._data.get(CONF_INVERT_POSITIONS, False) else position

        weather_entity = self._data[CONF_WEATHER_ENTITY]
        weather_state = self.hass.states.get(weather_entity)
        condition_now = weather_state.state if weather_state else "unknown"

        is_cloudy = condition_now in self._data.get(
            CONF_CLOUDY_CONDITIONS, DEFAULT_CLOUDY_CONDITIONS
        )

        if is_cloudy:
            position = self._data.get(CONF_POSITION_CLOUDY, DEFAULT_POSITION_CLOUDY)
            return 100 - position if self._data.get(CONF_INVERT_POSITIONS, False) else position

        sun_state = self.hass.states.get("sun.sun")
        azimuth = float(sun_state.attributes.get("azimuth", 0)) if sun_state else 0
        elevation = float(sun_state.attributes.get("elevation", 0)) if sun_state else 0

        orientation = self._data.get(CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION)
        tolerance = self._data.get(CONF_SUN_ANGLE_TOLERANCE, DEFAULT_SUN_ANGLE_TOLERANCE)
        min_elevation = self._data.get(CONF_MIN_SUN_ELEVATION, DEFAULT_MIN_SUN_ELEVATION)
        temp_threshold = self._data.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD)

        angle_diff = (azimuth - orientation) % 360
        if angle_diff > 180:
            angle_diff -= 360

        temp = self._get_temperature()

        is_sunny_in_angle = (
            abs(angle_diff) <= tolerance
            and elevation >= min_elevation
            and temp >= temp_threshold
        )

        if is_sunny_in_angle:
            position = self._data.get(
                CONF_POSITION_SUNNY_IN_ANGLE, DEFAULT_POSITION_SUNNY_IN_ANGLE
            )
        else:
            position = self._data.get(
                CONF_POSITION_SUNNY_OUTSIDE_ANGLE, DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE
            )

        return 100 - position if self._data.get(CONF_INVERT_POSITIONS, False) else position

    def _get_decision_reason(
        self, is_evening: bool = False, is_cloudy: bool = False
    ) -> str:
        """Return the reason for the target position."""
        if is_evening:
            return "evening"
        if is_cloudy:
            return "cloudy"

        sun_state = self.hass.states.get("sun.sun")
        azimuth = float(sun_state.attributes.get("azimuth", 0)) if sun_state else 0
        elevation = float(sun_state.attributes.get("elevation", 0)) if sun_state else 0

        orientation = self._data.get(CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION)
        tolerance = self._data.get(CONF_SUN_ANGLE_TOLERANCE, DEFAULT_SUN_ANGLE_TOLERANCE)
        min_elevation = self._data.get(CONF_MIN_SUN_ELEVATION, DEFAULT_MIN_SUN_ELEVATION)
        temp_threshold = self._data.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD)

        angle_diff = (azimuth - orientation) % 360
        if angle_diff > 180:
            angle_diff -= 360

        temp = self._get_temperature()

        if abs(angle_diff) > tolerance:
            return "sunny_outside_angle"
        if elevation < min_elevation:
            return "sunny_outside_angle"
        if temp < temp_threshold:
            return "sunny_outside_angle"
        return "sunny_in_angle"

    def _is_automation_enabled(self) -> bool:
        """Return whether automation is enabled via the switch entity."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if entry_data is None:
            return True
        switch = entry_data.get("switch")
        if switch is None:
            return True
        return switch.is_on

    async def async_update_position(self, is_evening: bool | None = None) -> None:
        """Update target position and move covers if needed."""
        if is_evening is not None:
            self._force_evening = is_evening
        is_evening = self._force_evening

        if not self._is_automation_enabled():
            self._decision_reason = "automation_disabled"
            self._should_move = False
            self.async_write_ha_state()
            return

        if self._is_quiet_time():
            self._decision_reason = "quiet_time"
            self._should_move = False
            self.async_write_ha_state()
            return

        if self._manual_activity_detected():
            self._decision_reason = "manual_activity_pause"
            self._should_move = False
            self.async_write_ha_state()
            return

        new_position = self._calculate_target_position(is_evening=is_evening)
        self._target_position = new_position

        if is_evening:
            self._decision_reason = "evening"
        else:
            weather_entity = self._data[CONF_WEATHER_ENTITY]
            weather_state = self.hass.states.get(weather_entity)
            condition_now = weather_state.state if weather_state else "unknown"
            is_cloudy = condition_now in self._data.get(
                CONF_CLOUDY_CONDITIONS, DEFAULT_CLOUDY_CONDITIONS
            )
            self._decision_reason = self._get_decision_reason(
                is_evening=False, is_cloudy=is_cloudy
            )

        # Calculate should_move
        current_positions = []
        for cover in self._data.get(CONF_COVERS, []):
            state = self.hass.states.get(cover)
            if state is None:
                continue
            try:
                pos = int(state.attributes.get("current_position", -1))
                if pos >= 0:
                    current_positions.append(pos)
            except (ValueError, TypeError):
                continue

        if current_positions:
            avg_current = sum(current_positions) // len(current_positions)
            min_change = self._data.get(CONF_MIN_POSITION_CHANGE, DEFAULT_MIN_POSITION_CHANGE)
            self._should_move = abs(new_position - avg_current) >= min_change
        else:
            self._should_move = True

        self.async_write_ha_state()

        if self._should_move and not self._data.get(CONF_TEST_MODE, False):
            now = dt_util.now()
            for cover in self._data.get(CONF_COVERS, []):
                await self.hass.services.async_call(
                    "cover",
                    "set_cover_position",
                    {"entity_id": cover, "position": new_position},
                    blocking=False,
                )
                self._last_sent_positions[cover] = (now, new_position)
