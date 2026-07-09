"""Decision engine for Simple Smart Cover.

Encapsulates the logic that turns weather, sun position, temperature and the
configured thresholds into a target cover position, a human readable decision
reason and a diagnostic details dictionary.

The engine is stateless apart from holding a reference to Home Assistant and a
callable that returns the current merged config (data + options). Every call
re-reads the live state so option changes take effect immediately.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CLOUDY_CONDITIONS,
    CONF_INVERT_POSITIONS,
    CONF_MIN_SUN_ELEVATION,
    CONF_POSITION_CLOUDY,
    CONF_POSITION_EVENING,
    CONF_POSITION_SUNNY_IN_ANGLE,
    CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
    CONF_SUN_ANGLE_TOLERANCE,
    CONF_TEMP_FORECAST_ENTITY,
    CONF_TEMP_SOURCE,
    CONF_TEMP_THRESHOLD,
    CONF_USE_FORECAST_MAX_TEMP,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_ORIENTATION,
    DEFAULT_CLOUDY_CONDITIONS,
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_POSITION_CLOUDY,
    DEFAULT_POSITION_EVENING,
    DEFAULT_POSITION_SUNNY_IN_ANGLE,
    DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
    DEFAULT_SUN_ANGLE_TOLERANCE,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_WINDOW_ORIENTATION,
)

_LOGGER = logging.getLogger(__name__)

# Sun entity used to read azimuth and elevation.
SUN_ENTITY_ID = "sun.sun"


# ---------------------------------------------------------------------------
# Value objects describing a single decision input snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SunState:
    """Sun position at the time of the decision."""

    azimuth: float
    elevation: float


@dataclass(frozen=True)
class Thresholds:
    """Configured thresholds used for the sunny-in-angle check."""

    sun_angle_tolerance: float
    min_sun_elevation: float
    temp_threshold: float


@dataclass
class DecisionContext:
    """Snapshot of every value that drives a single decision.

    Building the context once per evaluation avoids the three-fold
    recomputation of sun state, angle difference and temperature that the
    original cover entity performed.
    """

    is_evening: bool
    is_cloudy: bool
    weather_condition: str
    sun: SunState
    temperature: float
    window_orientation: float
    angle_diff: float
    thresholds: Thresholds

    @property
    def angle_in_range(self) -> bool:
        """True if the sun azimuth is within the tolerance window."""
        return abs(self.angle_diff) <= self.thresholds.sun_angle_tolerance

    @property
    def elevation_high_enough(self) -> bool:
        """True if the sun is above the minimum elevation."""
        return self.sun.elevation >= self.thresholds.min_sun_elevation

    @property
    def temp_high_enough(self) -> bool:
        """True if the temperature is at or above the configured threshold."""
        return self.temperature >= self.thresholds.temp_threshold

    @property
    def is_sunny_in_angle(self) -> bool:
        """True when shading is desired: sun in window, high enough and warm."""
        return (
            self.angle_in_range
            and self.elevation_high_enough
            and self.temp_high_enough
        )


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------


class DecisionEngine:
    """Builds a DecisionContext and derives position, reason and details."""

    def __init__(
        self,
        hass: HomeAssistant,
        data_provider: Callable[[], dict[str, Any]],
        name: str,
    ) -> None:
        """Store references; no state is read until a method is called."""
        self._hass = hass
        self._data_provider = data_provider
        self._name = name

    # -- raw state helpers -------------------------------------------------

    def _data(self) -> dict[str, Any]:
        """Return the current merged config (data + options)."""
        return self._data_provider()

    def _get_state_float(self, entity_id: str) -> float | None:
        """Read a state value as float, or None if unavailable."""
        state = self._hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_state_attr_float(self, entity_id: str, attribute: str) -> float | None:
        """Read a state attribute as float, or None if unavailable."""
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        value = state.attributes.get(attribute)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    # -- individual inputs -------------------------------------------------

    def get_weather_condition(self) -> str:
        """Return the current weather condition, or 'unknown' if unavailable."""
        weather_entity = self._data()[CONF_WEATHER_ENTITY]
        weather_state = self._hass.states.get(weather_entity)
        if weather_state is None:
            return "unknown"
        return weather_state.state

    def is_weather_available(self) -> bool:
        """True if the configured weather entity has a usable state."""
        weather_entity = self._data()[CONF_WEATHER_ENTITY]
        weather_state = self._hass.states.get(weather_entity)
        return (
            weather_state is not None
            and weather_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        )

    def get_sun_state(self) -> SunState:
        """Return the current sun azimuth and elevation (0,0 if missing)."""
        sun_state = self._hass.states.get(SUN_ENTITY_ID)
        if sun_state is None:
            return SunState(azimuth=0.0, elevation=0.0)
        azimuth = float(sun_state.attributes.get("azimuth", 0))
        elevation = float(sun_state.attributes.get("elevation", 0))
        return SunState(azimuth=azimuth, elevation=elevation)

    def get_temperature(self) -> float:
        """Return the temperature used for the decision.

        Resolution order:
        1. Forecast max temperature entity (if enabled and configured).
        2. Explicit temperature sensor (if configured).
        3. Weather entity 'temperature' attribute.
        4. 0.0 as a last resort (with a warning).
        """
        data = self._data()
        weather_entity = data[CONF_WEATHER_ENTITY]
        fallback = self._get_state_attr_float(weather_entity, "temperature")

        if data.get(CONF_USE_FORECAST_MAX_TEMP, False):
            forecast_entities = data.get(CONF_TEMP_FORECAST_ENTITY)
            if forecast_entities:
                forecast_entity = self._first_or_value(forecast_entities)
                val = self._get_state_float(forecast_entity)
                if val is not None:
                    return val
                _LOGGER.warning(
                    "Forecast temperature entity %s unavailable, using fallback",
                    forecast_entity,
                )
                if fallback is not None:
                    return fallback

        temp_sources = data.get(CONF_TEMP_SOURCE)
        if temp_sources:
            temp_source = self._first_or_value(temp_sources)
            val = self._get_state_float(temp_source)
            if val is not None:
                return val
            _LOGGER.warning(
                "Temperature source %s unavailable, using fallback",
                temp_source,
            )
            if fallback is not None:
                return fallback

        if fallback is not None:
            return fallback
        _LOGGER.warning(
            "No temperature source available for %s, using 0.0",
            self._name,
        )
        return 0.0

    # -- context assembly --------------------------------------------------

    def build_context(
        self,
        is_evening: bool,
        is_cloudy: bool | None = None,
    ) -> DecisionContext:
        """Build a DecisionContext from the live state.

        If is_cloudy is None it is derived from the current weather condition.
        Passing it explicitly is useful for early-return paths (quiet time,
        manual pause, weather unavailable) where the original code forced
        is_cloudy=False.
        """
        data = self._data()
        condition = self.get_weather_condition()
        if is_cloudy is None:
            cloudy_conditions = data.get(
                CONF_CLOUDY_CONDITIONS, DEFAULT_CLOUDY_CONDITIONS
            )
            is_cloudy = condition in cloudy_conditions

        sun = self.get_sun_state()
        orientation = data.get(
            CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION
        )
        thresholds = Thresholds(
            sun_angle_tolerance=data.get(
                CONF_SUN_ANGLE_TOLERANCE, DEFAULT_SUN_ANGLE_TOLERANCE
            ),
            min_sun_elevation=data.get(
                CONF_MIN_SUN_ELEVATION, DEFAULT_MIN_SUN_ELEVATION
            ),
            temp_threshold=data.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
        )
        angle_diff = self._angle_diff(sun.azimuth, orientation)
        temperature = self.get_temperature()

        return DecisionContext(
            is_evening=is_evening,
            is_cloudy=is_cloudy,
            weather_condition=condition,
            sun=sun,
            temperature=temperature,
            window_orientation=orientation,
            angle_diff=angle_diff,
            thresholds=thresholds,
        )

    # -- outputs -----------------------------------------------------------

    def target_position(self, ctx: DecisionContext) -> int:
        """Return the target cover position for the given context."""
        if ctx.is_evening:
            position = self._data().get(
                CONF_POSITION_EVENING, DEFAULT_POSITION_EVENING
            )
            return self._apply_invert(position)

        if ctx.is_cloudy:
            position = self._data().get(
                CONF_POSITION_CLOUDY, DEFAULT_POSITION_CLOUDY
            )
            return self._apply_invert(position)

        if ctx.is_sunny_in_angle:
            position = self._data().get(
                CONF_POSITION_SUNNY_IN_ANGLE, DEFAULT_POSITION_SUNNY_IN_ANGLE
            )
        else:
            position = self._data().get(
                CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
                DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
            )
        return self._apply_invert(position)

    def reason(self, ctx: DecisionContext) -> str:
        """Return the decision reason string for the given context.

        Only produces the daytime/evening reasons. Special reasons such as
        'quiet_time', 'manual_activity_pause' and 'weather_unavailable' are
        set directly by the cover orchestrator.
        """
        if ctx.is_evening:
            return "evening"
        if ctx.is_cloudy:
            return "cloudy"
        return "sunny_in_angle" if ctx.is_sunny_in_angle else "sunny_outside_angle"

    def details(self, ctx: DecisionContext) -> dict[str, Any]:
        """Return the diagnostic details dictionary for the given context."""
        return {
            "is_evening": ctx.is_evening,
            "is_cloudy": ctx.is_cloudy,
            "weather_condition": ctx.weather_condition,
            "sun_azimuth": round(ctx.sun.azimuth, 2),
            "sun_elevation": round(ctx.sun.elevation, 2),
            "window_orientation": ctx.window_orientation,
            "angle_diff": round(ctx.angle_diff, 2),
            "temperature": round(ctx.temperature, 2),
            "thresholds": {
                "sun_angle_tolerance": ctx.thresholds.sun_angle_tolerance,
                "min_sun_elevation": ctx.thresholds.min_sun_elevation,
                "temp_threshold": ctx.thresholds.temp_threshold,
            },
            "checks": {
                "angle_in_range": ctx.angle_in_range,
                "elevation_high_enough": ctx.elevation_high_enough,
                "temp_high_enough": ctx.temp_high_enough,
            },
        }

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _angle_diff(azimuth: float, orientation: float) -> float:
        """Shortest signed difference between sun azimuth and window orientation.

        Result is in the range [-180, 180]; 0 means the sun is exactly in front
        of the window.
        """
        diff = (azimuth - orientation) % 360
        if diff > 180:
            diff -= 360
        return diff

    def _apply_invert(self, position: int) -> int:
        """Apply the invert-positions config flag to a raw position."""
        if self._data().get(CONF_INVERT_POSITIONS, False):
            return 100 - position
        return position

    @staticmethod
    def _first_or_value(value: Any) -> str:
        """Return the first element if value is a list, otherwise value itself.

        Config entries may store a single entity id string or a list of ids
        depending on the selector version that created them.
        """
        if isinstance(value, list):
            return value[0]
        return value


# Re-exported so callers can import all decision types from one place.
__all__ = [
    "DecisionContext",
    "DecisionEngine",
    "SunState",
    "Thresholds",
]
