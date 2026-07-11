"""Voluptuous schema builders for the Simple Smart Cover config/options flow.

The schema is large because the integration exposes many tunable parameters.
Keeping the selector construction here lets the config flow module focus on
flow control and validation.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_CLOUDY_CONDITIONS,
    CONF_COVERS,
    CONF_ENABLE_EVENING,
    CONF_ENABLE_MANUAL_ACTIVITY_PAUSE,
    CONF_ENABLE_MORNING,
    CONF_ENABLE_QUIET_MODE,
    CONF_ENABLE_REEVALUATION,
    CONF_INVERT_POSITIONS,
    CONF_MANUAL_ACTIVITY_DURATION,
    CONF_MIN_POSITION_CHANGE,
    CONF_MIN_SUN_ELEVATION,
    CONF_MORNING_TIME,
    CONF_POSITION_CLOUDY,
    CONF_POSITION_EVENING,
    CONF_POSITION_SUNNY_IN_ANGLE,
    CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_REEVALUATE_INTERVAL,
    CONF_SUN_ANGLE_TOLERANCE,
    CONF_TEMP_FORECAST_ENTITY,
    CONF_TEMP_SOURCE,
    CONF_TEMP_THRESHOLD,
    CONF_TEST_MODE,
    CONF_USE_FORECAST_MAX_TEMP,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_ORIENTATION,
    DEFAULT_CLOUDY_CONDITIONS,
    DEFAULT_MANUAL_ACTIVITY_DURATION,
    DEFAULT_MIN_POSITION_CHANGE,
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_MORNING_TIME,
    DEFAULT_POSITION_CLOUDY,
    DEFAULT_POSITION_EVENING,
    DEFAULT_POSITION_SUNNY_IN_ANGLE,
    DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
    DEFAULT_REEVALUATE_INTERVAL,
    DEFAULT_SUN_ANGLE_TOLERANCE,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_WINDOW_ORIENTATION,
    REEVALUATE_INTERVAL_LABELS,
    WEATHER_CONDITION_LABELS,
)

# Optional entity-selector keys that voluptuous omits when cleared by the user.
OPTIONAL_ENTITY_KEYS = [CONF_TEMP_SOURCE, CONF_TEMP_FORECAST_ENTITY]


# ---------------------------------------------------------------------------
# Selector factories
# ---------------------------------------------------------------------------


def _slider(
    min_val: float,
    max_val: float,
    step: float,
    unit: str,
) -> selector.NumberSelector:
    """Build a slider selector with the given range and unit."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_val,
            max=max_val,
            step=step,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.SLIDER,
        )
    )


def _cover_selector() -> selector.EntitySelector:
    """Entity selector allowing multiple cover entities."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=COVER_DOMAIN, multiple=True)
    )


def _weather_selector() -> selector.EntitySelector:
    """Entity selector for a single weather entity."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=WEATHER_DOMAIN, multiple=False)
    )


def _temp_sensor_selector() -> selector.EntitySelector:
    """Entity selector for a single temperature sensor."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            device_class="temperature", multiple=False
        )
    )


def _optional_default(defaults: dict[str, Any], key: str) -> dict[str, Any]:
    """Return default kwargs for an optional entity selector.

    Voluptuous drops optional keys that have no default, so we only pass a
    default when the user previously selected a value. This lets the field
    appear empty when cleared.
    """
    value = defaults.get(key)
    if value:
        return {"default": value}
    return {}


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------


def build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the full config/options schema pre-filled from defaults."""
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME)
            ): str,
            vol.Required(
                CONF_COVERS, default=defaults.get(CONF_COVERS, [])
            ): _cover_selector(),
            vol.Required(
                CONF_WEATHER_ENTITY, default=defaults.get(CONF_WEATHER_ENTITY)
            ): _weather_selector(),
            vol.Optional(
                CONF_MORNING_TIME,
                default=defaults.get(CONF_MORNING_TIME, DEFAULT_MORNING_TIME),
            ): str,
            vol.Optional(
                CONF_ENABLE_MORNING, default=defaults.get(CONF_ENABLE_MORNING, True)
            ): bool,
            vol.Optional(
                CONF_ENABLE_EVENING, default=defaults.get(CONF_ENABLE_EVENING, True)
            ): bool,
            vol.Optional(
                CONF_WINDOW_ORIENTATION,
                default=defaults.get(CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION),
            ): _slider(0, 360, 1, "°"),
            vol.Optional(
                CONF_SUN_ANGLE_TOLERANCE,
                default=defaults.get(
                    CONF_SUN_ANGLE_TOLERANCE, DEFAULT_SUN_ANGLE_TOLERANCE
                ),
            ): _slider(0, 180, 1, "°"),
            vol.Optional(
                CONF_MIN_SUN_ELEVATION,
                default=defaults.get(
                    CONF_MIN_SUN_ELEVATION, DEFAULT_MIN_SUN_ELEVATION
                ),
            ): _slider(-90, 90, 1, "°"),
            vol.Optional(
                CONF_TEMP_THRESHOLD,
                default=defaults.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
            ): _slider(-20, 45, 0.5, "°C"),
            vol.Optional(
                CONF_TEMP_SOURCE, **_optional_default(defaults, CONF_TEMP_SOURCE)
            ): _temp_sensor_selector(),
            vol.Optional(
                CONF_USE_FORECAST_MAX_TEMP,
                default=defaults.get(CONF_USE_FORECAST_MAX_TEMP, False),
            ): bool,
            vol.Optional(
                CONF_TEMP_FORECAST_ENTITY,
                **_optional_default(defaults, CONF_TEMP_FORECAST_ENTITY),
            ): _temp_sensor_selector(),
            vol.Optional(
                CONF_CLOUDY_CONDITIONS,
                default=defaults.get(CONF_CLOUDY_CONDITIONS, DEFAULT_CLOUDY_CONDITIONS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=WEATHER_CONDITION_LABELS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_POSITION_SUNNY_IN_ANGLE,
                default=defaults.get(
                    CONF_POSITION_SUNNY_IN_ANGLE, DEFAULT_POSITION_SUNNY_IN_ANGLE
                ),
            ): _slider(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
                default=defaults.get(
                    CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
                    DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
                ),
            ): _slider(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_CLOUDY,
                default=defaults.get(CONF_POSITION_CLOUDY, DEFAULT_POSITION_CLOUDY),
            ): _slider(0, 100, 1, "%"),
            vol.Optional(
                CONF_POSITION_EVENING,
                default=defaults.get(CONF_POSITION_EVENING, DEFAULT_POSITION_EVENING),
            ): _slider(0, 100, 1, "%"),
            vol.Optional(
                CONF_INVERT_POSITIONS,
                default=defaults.get(CONF_INVERT_POSITIONS, False),
            ): bool,
            vol.Optional(
                CONF_ENABLE_QUIET_MODE,
                default=defaults.get(CONF_ENABLE_QUIET_MODE, False),
            ): bool,
            vol.Optional(
                CONF_QUIET_START,
                default=defaults.get(CONF_QUIET_START, "22:00:00"),
            ): str,
            vol.Optional(
                CONF_QUIET_END,
                default=defaults.get(CONF_QUIET_END, "07:00:00"),
            ): str,
            vol.Optional(
                CONF_ENABLE_REEVALUATION,
                default=defaults.get(CONF_ENABLE_REEVALUATION, True),
            ): bool,
            vol.Optional(
                CONF_REEVALUATE_INTERVAL,
                default=defaults.get(
                    CONF_REEVALUATE_INTERVAL, DEFAULT_REEVALUATE_INTERVAL
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=REEVALUATE_INTERVAL_LABELS,
                    multiple=False,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_MIN_POSITION_CHANGE,
                default=defaults.get(
                    CONF_MIN_POSITION_CHANGE, DEFAULT_MIN_POSITION_CHANGE
                ),
            ): _slider(0, 100, 1, "%"),
            vol.Optional(
                CONF_ENABLE_MANUAL_ACTIVITY_PAUSE,
                default=defaults.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, True),
            ): bool,
            vol.Optional(
                CONF_MANUAL_ACTIVITY_DURATION,
                default=defaults.get(
                    CONF_MANUAL_ACTIVITY_DURATION, DEFAULT_MANUAL_ACTIVITY_DURATION
                ),
            ): _slider(1, 180, 1, "min"),
            vol.Optional(
                CONF_TEST_MODE,
                default=defaults.get(CONF_TEST_MODE, False),
            ): bool,
        }
    )


def build_duplicate_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the reduced schema for the duplicate-configure step.

    Only the fields that must be unique per group (name, covers, orientation)
    are editable; everything else is inherited from the source entry.
    """
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME)
            ): selector.TextSelector(),
            vol.Required(
                CONF_COVERS, default=defaults.get(CONF_COVERS, [])
            ): _cover_selector(),
            vol.Optional(
                CONF_WINDOW_ORIENTATION,
                default=defaults.get(CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION),
            ): _slider(0, 360, 1, "°"),
        }
    )


def null_cleared_optional_keys(user_input: dict[str, Any]) -> None:
    """Set optional entity keys to None when voluptuous omitted them.

    When a user clears an optional entity selector, voluptuous does not include
    the key in user_input. We explicitly store None so the saved config reflects
    the cleared state instead of keeping a stale previous value.
    """
    for key in OPTIONAL_ENTITY_KEYS:
        if key not in user_input:
            user_input[key] = None
