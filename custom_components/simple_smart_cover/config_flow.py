"""Config flow for Simple Smart Cover integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    DEFAULT_MORNING_TIME,
    DEFAULT_WINDOW_ORIENTATION,
    DEFAULT_SUN_ANGLE_TOLERANCE,
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_CLOUDY_CONDITIONS,
    DEFAULT_POSITION_SUNNY_IN_ANGLE,
    DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
    DEFAULT_POSITION_CLOUDY,
    DEFAULT_POSITION_EVENING,
    DEFAULT_REEVALUATE_INTERVAL,
    DEFAULT_MIN_POSITION_CHANGE,
    DEFAULT_MANUAL_ACTIVITY_DURATION,
)


class SimpleSmartCoverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Simple Smart Cover."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_COVERS): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=COVER_DOMAIN,
                        multiple=True,
                    )
                ),
                vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=WEATHER_DOMAIN,
                        multiple=False,
                    )
                ),
                vol.Optional(CONF_MORNING_TIME, default=DEFAULT_MORNING_TIME): str,
                vol.Optional(CONF_ENABLE_MORNING, default=True): bool,
                vol.Optional(CONF_ENABLE_EVENING, default=True): bool,
                vol.Optional(
                    CONF_WINDOW_ORIENTATION, default=DEFAULT_WINDOW_ORIENTATION
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=360,
                        step=1,
                        unit_of_measurement="°",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_SUN_ANGLE_TOLERANCE, default=DEFAULT_SUN_ANGLE_TOLERANCE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=180,
                        step=1,
                        unit_of_measurement="°",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_MIN_SUN_ELEVATION, default=DEFAULT_MIN_SUN_ELEVATION
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-90,
                        max=90,
                        step=1,
                        unit_of_measurement="°",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_TEMP_THRESHOLD, default=DEFAULT_TEMP_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-20,
                        max=45,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(CONF_TEMP_SOURCE): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        device_class="temperature",
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_USE_FORECAST_MAX_TEMP, default=False): bool,
                vol.Optional(CONF_TEMP_FORECAST_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        device_class="temperature",
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_CLOUDY_CONDITIONS, default=DEFAULT_CLOUDY_CONDITIONS
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"label": "Sonnig", "value": "sunny"},
                            {"label": "Klar (Nacht)", "value": "clear-night"},
                            {"label": "Teilweise bewölkt", "value": "partlycloudy"},
                            {"label": "Bewölkt", "value": "cloudy"},
                            {"label": "Nebel", "value": "fog"},
                            {"label": "Regen", "value": "rainy"},
                            {"label": "Starker Regen", "value": "pouring"},
                            {"label": "Schnee", "value": "snowy"},
                            {"label": "Schneeregen", "value": "snowy-rainy"},
                            {"label": "Hagel", "value": "hail"},
                            {"label": "Gewitter", "value": "lightning"},
                            {"label": "Gewitter mit Regen", "value": "lightning-rainy"},
                            {"label": "Windig", "value": "windy"},
                            {"label": "Windig, wechselhaft", "value": "windy-variant"},
                            {"label": "Außergewöhnlich", "value": "exceptional"},
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_POSITION_SUNNY_IN_ANGLE, default=DEFAULT_POSITION_SUNNY_IN_ANGLE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
                    default=DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(CONF_POSITION_CLOUDY, default=DEFAULT_POSITION_CLOUDY): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(CONF_POSITION_EVENING, default=DEFAULT_POSITION_EVENING): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(CONF_INVERT_POSITIONS, default=False): bool,
                vol.Optional(CONF_ENABLE_QUIET_MODE, default=False): bool,
                vol.Optional(CONF_QUIET_START, default="22:00:00"): str,
                vol.Optional(CONF_QUIET_END, default="07:00:00"): str,
                vol.Optional(CONF_ENABLE_REEVALUATION, default=True): bool,
                vol.Optional(
                    CONF_REEVALUATE_INTERVAL, default=DEFAULT_REEVALUATE_INTERVAL
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"label": "15 Minuten", "value": "15"},
                            {"label": "30 Minuten", "value": "30"},
                            {"label": "60 Minuten", "value": "60"},
                        ],
                        multiple=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_MIN_POSITION_CHANGE, default=DEFAULT_MIN_POSITION_CHANGE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, default=True): bool,
                vol.Optional(
                    CONF_MANUAL_ACTIVITY_DURATION,
                    default=DEFAULT_MANUAL_ACTIVITY_DURATION,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=120,
                        step=1,
                        unit_of_measurement="Min",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
