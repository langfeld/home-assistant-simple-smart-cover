"""Config flow for Simple Smart Cover integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
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
    CONF_TEST_MODE,
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


def _optional_default(defaults: dict[str, Any], key: str) -> dict[str, Any]:
    """Return default kwargs for optional entity selectors."""
    value = defaults.get(key)
    if value:
        return {"default": value}
    return {}


def _optional_entities(keys: list[str], user_input: dict[str, Any]) -> None:
    """Set optional keys to None if they were cleared and omitted by voluptuous."""
    for key in keys:
        if key not in user_input:
            user_input[key] = None


# Optional fields that must be explicitly nulled when cleared by the user.
_OPTIONAL_KEYS = [
    CONF_TEMP_SOURCE,
    CONF_TEMP_FORECAST_ENTITY,
]


def _get_existing_entries(hass: HomeAssistant) -> list[config_entries.ConfigEntry]:
    """Return existing Simple Smart Cover config entries."""
    return hass.config_entries.async_entries(DOMAIN)


def _ensure_unique_name(
    hass: HomeAssistant, name: str, suffix: str = "Kopie"
) -> str:
    """Ensure the config entry name is unique."""
    existing_names = {
        e.data.get(CONF_NAME) for e in _get_existing_entries(hass) if CONF_NAME in e.data
    }

    if name not in existing_names:
        return name

    suffixed = f"{name} ({suffix})"
    if suffixed not in existing_names:
        return suffixed

    counter = 2
    while f"{name} ({suffix} {counter})" in existing_names:
        counter += 1
    return f"{name} ({suffix} {counter})"


def _get_used_covers(hass: HomeAssistant) -> set[str]:
    """Return covers already used by other Simple Smart Cover entries."""
    used: set[str] = set()
    for entry in _get_existing_entries(hass):
        used.update(entry.data.get(CONF_COVERS, []))
        used.update(entry.options.get(CONF_COVERS, []))
    return used


def _get_duplicate_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return schema for the duplicate configuration step."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME)
            ): selector.TextSelector(),
            vol.Required(
                CONF_COVERS, default=defaults.get(CONF_COVERS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=COVER_DOMAIN,
                    multiple=True,
                )
            ),
            vol.Optional(
                CONF_WINDOW_ORIENTATION,
                default=defaults.get(CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=360,
                    step=1,
                    unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _get_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the schema used by both config and options flow."""
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME)
            ): str,
            vol.Required(
                CONF_COVERS, default=defaults.get(CONF_COVERS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=COVER_DOMAIN,
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_WEATHER_ENTITY, default=defaults.get(CONF_WEATHER_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=WEATHER_DOMAIN,
                    multiple=False,
                )
            ),
            vol.Optional(
                CONF_MORNING_TIME, default=defaults.get(CONF_MORNING_TIME, DEFAULT_MORNING_TIME)
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
                CONF_SUN_ANGLE_TOLERANCE,
                default=defaults.get(CONF_SUN_ANGLE_TOLERANCE, DEFAULT_SUN_ANGLE_TOLERANCE),
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
                CONF_MIN_SUN_ELEVATION,
                default=defaults.get(CONF_MIN_SUN_ELEVATION, DEFAULT_MIN_SUN_ELEVATION),
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
                CONF_TEMP_THRESHOLD,
                default=defaults.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-20,
                    max=45,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_TEMP_SOURCE, **_optional_default(defaults, CONF_TEMP_SOURCE)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    device_class="temperature",
                    multiple=False,
                )
            ),
            vol.Optional(
                CONF_USE_FORECAST_MAX_TEMP,
                default=defaults.get(CONF_USE_FORECAST_MAX_TEMP, False),
            ): bool,
            vol.Optional(
                CONF_TEMP_FORECAST_ENTITY, **_optional_default(defaults, CONF_TEMP_FORECAST_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    device_class="temperature",
                    multiple=False,
                )
            ),
            vol.Optional(
                CONF_CLOUDY_CONDITIONS,
                default=defaults.get(CONF_CLOUDY_CONDITIONS, DEFAULT_CLOUDY_CONDITIONS),
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
                CONF_POSITION_SUNNY_IN_ANGLE,
                default=defaults.get(CONF_POSITION_SUNNY_IN_ANGLE, DEFAULT_POSITION_SUNNY_IN_ANGLE),
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
                default=defaults.get(
                    CONF_POSITION_SUNNY_OUTSIDE_ANGLE, DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE
                ),
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
                CONF_POSITION_CLOUDY,
                default=defaults.get(CONF_POSITION_CLOUDY, DEFAULT_POSITION_CLOUDY),
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
                CONF_POSITION_EVENING,
                default=defaults.get(CONF_POSITION_EVENING, DEFAULT_POSITION_EVENING),
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
                default=defaults.get(CONF_REEVALUATE_INTERVAL, DEFAULT_REEVALUATE_INTERVAL),
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
                CONF_MIN_POSITION_CHANGE,
                default=defaults.get(CONF_MIN_POSITION_CHANGE, DEFAULT_MIN_POSITION_CHANGE),
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
                CONF_ENABLE_MANUAL_ACTIVITY_PAUSE,
                default=defaults.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, True),
            ): bool,
            vol.Optional(
                CONF_MANUAL_ACTIVITY_DURATION,
                default=defaults.get(CONF_MANUAL_ACTIVITY_DURATION, DEFAULT_MANUAL_ACTIVITY_DURATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=120,
                    step=1,
                    unit_of_measurement="Min",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_TEST_MODE,
                default=defaults.get(CONF_TEST_MODE, False),
            ): bool,
        }
    )


class SimpleSmartCoverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Simple Smart Cover."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._duplicate_source_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SimpleSmartCoverOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        menu_options = ["create_new"]
        if _get_existing_entries(self.hass):
            menu_options.append("duplicate_existing")

        return self.async_show_menu(
            step_id="user",
            menu_options=menu_options,
        )

    async def async_step_create_new(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle creating a new group."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _optional_entities(_OPTIONAL_KEYS, user_input)
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="create_new",
            data_schema=_get_schema(),
            errors=errors,
        )

    async def async_step_duplicate_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start duplication flow."""
        return await self.async_step_duplicate_select(user_input)

    async def async_step_duplicate_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select source entry to duplicate."""
        if user_input is not None:
            entry_id = user_input["source_entry"]
            source_entry = self.hass.config_entries.async_get_entry(entry_id)
            if source_entry is None:
                return self.async_abort(reason="source_not_found")
            self._duplicate_source_entry = source_entry
            return await self.async_step_duplicate_configure()

        entries = _get_existing_entries(self.hass)
        if not entries:
            return self.async_abort(reason="source_not_found")

        return self.async_show_form(
            step_id="duplicate_select",
            data_schema=vol.Schema(
                {
                    vol.Required("source_entry"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": e.entry_id, "label": e.title}
                                for e in entries
                            ],
                            multiple=False,
                        )
                    )
                }
            ),
        )

    async def async_step_duplicate_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure unique fields for the duplicated group."""
        source_entry = self._duplicate_source_entry
        if source_entry is None:
            return self.async_abort(reason="source_not_found")

        if user_input is not None:
            new_name = _ensure_unique_name(
                self.hass, user_input[CONF_NAME], suffix="Kopie"
            )

            # Merge data and options from source, then override unique fields
            new_data = {**source_entry.data, **source_entry.options}
            new_data[CONF_NAME] = new_name
            new_data[CONF_COVERS] = user_input[CONF_COVERS]
            new_data[CONF_WINDOW_ORIENTATION] = user_input[CONF_WINDOW_ORIENTATION]

            # Remove keys that belong in options if they exist there
            new_options = dict(source_entry.options)
            new_options.pop(CONF_NAME, None)
            new_options.pop(CONF_COVERS, None)
            new_options.pop(CONF_WINDOW_ORIENTATION, None)

            # Optional keys cleared in duplicate step must be nulled
            _optional_entities(_OPTIONAL_KEYS, new_data)

            return self.async_create_entry(
                title=new_name,
                data=new_data,
                options=new_options,
            )

        defaults = {**source_entry.data, **source_entry.options}
        defaults[CONF_NAME] = _ensure_unique_name(
            self.hass, defaults.get(CONF_NAME, ""), suffix="Kopie"
        )

        # Warn about covers already used by other groups
        used_covers = _get_used_covers(self.hass)
        source_covers = set(source_entry.data.get(CONF_COVERS, []))
        source_covers.update(source_entry.options.get(CONF_COVERS, []))
        other_used = used_covers - source_covers
        warning = ""
        if other_used:
            warning = (
                "Achtung: Diese Covers werden bereits von anderen Gruppen "
                f"verwendet: {', '.join(sorted(other_used))}"
            )

        return self.async_show_form(
            step_id="duplicate_configure",
            data_schema=_get_duplicate_schema(defaults),
            description_placeholders={
                "source_name": source_entry.title,
                "warning": warning,
            },
        )


class SimpleSmartCoverOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Simple Smart Cover."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            _optional_entities(_OPTIONAL_KEYS, user_input)
            return self.async_create_entry(title="", data=user_input)

        # Merge saved data and options so existing values are pre-filled
        defaults = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=_get_schema(defaults),
        )
