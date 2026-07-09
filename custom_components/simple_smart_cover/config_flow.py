"""Config and options flow for Simple Smart Cover integration.

The flow supports creating a new cover group, editing it via the options flow,
and duplicating an existing group. Schema construction lives in schemas.py;
this module handles flow control, validation and uniqueness checks.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_COVERS,
    CONF_MORNING_TIME,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_WINDOW_ORIENTATION,
    COPY_SUFFIX,
    DOMAIN,
    is_valid_time,
)
from .schemas import (
    build_duplicate_schema,
    build_schema,
    null_cleared_optional_keys,
)

# Time-format fields validated across config and options flow.
_TIME_FIELDS = (CONF_MORNING_TIME, CONF_QUIET_START, CONF_QUIET_END)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_time_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate time-format fields. Return a dict of field -> error_key."""
    errors: dict[str, str] = {}
    for time_key in _TIME_FIELDS:
        value = user_input.get(time_key)
        if value and not is_valid_time(value):
            errors[time_key] = "invalid_time"
    return errors


# ---------------------------------------------------------------------------
# Uniqueness helpers
# ---------------------------------------------------------------------------


def _get_existing_entries(hass: HomeAssistant) -> list[config_entries.ConfigEntry]:
    """Return existing Simple Smart Cover config entries."""
    return hass.config_entries.async_entries(DOMAIN)


def _get_existing_names(
    hass: HomeAssistant, exclude_entry_id: str | None = None
) -> set[str]:
    """Return names already used by other Simple Smart Cover entries."""
    existing_names: set[str] = set()
    for e in _get_existing_entries(hass):
        if e.entry_id == exclude_entry_id:
            continue
        name = e.data.get(CONF_NAME)
        if name:
            existing_names.add(name)
    return existing_names


def _ensure_unique_name(
    hass: HomeAssistant, name: str, suffix: str = COPY_SUFFIX
) -> str:
    """Ensure the config entry name is unique by appending a suffix if needed."""
    existing_names = _get_existing_names(hass)

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


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------


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
        """Show the initial menu: create new or duplicate an existing group."""
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
            errors = _validate_time_fields(user_input)

            if user_input[CONF_NAME] in _get_existing_names(self.hass):
                errors[CONF_NAME] = "name_exists"

            if not errors:
                null_cleared_optional_keys(user_input)
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="create_new",
            data_schema=build_schema(),
            errors=errors,
        )

    async def async_step_duplicate_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the duplication flow."""
        return await self.async_step_duplicate_select(user_input)

    async def async_step_duplicate_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select the source entry to duplicate."""
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
        """Configure the unique fields for the duplicated group."""
        source_entry = self._duplicate_source_entry
        if source_entry is None:
            return self.async_abort(reason="source_not_found")

        if user_input is not None:
            new_name = _ensure_unique_name(
                self.hass, user_input[CONF_NAME], suffix=COPY_SUFFIX
            )

            # Merge data and options from source, then override unique fields.
            new_data = {**source_entry.data, **source_entry.options}
            new_data[CONF_NAME] = new_name
            new_data[CONF_COVERS] = user_input[CONF_COVERS]
            new_data[CONF_WINDOW_ORIENTATION] = user_input[CONF_WINDOW_ORIENTATION]

            # Keys that belong in options must not be duplicated into data.
            new_options = dict(source_entry.options)
            new_options.pop(CONF_NAME, None)
            new_options.pop(CONF_COVERS, None)
            new_options.pop(CONF_WINDOW_ORIENTATION, None)

            null_cleared_optional_keys(new_data)

            return self.async_create_entry(
                title=new_name,
                data=new_data,
                options=new_options,
            )

        defaults = {**source_entry.data, **source_entry.options}
        defaults[CONF_NAME] = _ensure_unique_name(
            self.hass, defaults.get(CONF_NAME, ""), suffix=COPY_SUFFIX
        )

        # Warn about covers already used by other groups.
        used_covers = _get_used_covers(self.hass)
        source_covers = set(source_entry.data.get(CONF_COVERS, []))
        source_covers.update(source_entry.options.get(CONF_COVERS, []))
        other_used = used_covers - source_covers
        warning = ""
        if other_used:
            warning = (
                "Warning: these covers are already used by other groups: "
                f"{', '.join(sorted(other_used))}"
            )

        return self.async_show_form(
            step_id="duplicate_configure",
            data_schema=build_duplicate_schema(defaults),
            description_placeholders={
                "source_name": source_entry.title,
                "warning": warning,
            },
        )


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class SimpleSmartCoverOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Simple Smart Cover."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the integration options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_time_fields(user_input)

            # Validate unique name (excluding this entry).
            name = user_input.get(CONF_NAME)
            if name and name in _get_existing_names(
                self.hass, exclude_entry_id=self._config_entry.entry_id
            ):
                errors[CONF_NAME] = "name_exists"

            if not errors:
                # A name change updates the entry title and data[CONF_NAME].
                if name is not None and name != self._config_entry.title:
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        title=name,
                        data={**self._config_entry.data, CONF_NAME: name},
                    )

                # CONF_NAME is handled above; keep it out of options data.
                user_input.pop(CONF_NAME, None)

                null_cleared_optional_keys(user_input)
                return self.async_create_entry(title="", data=user_input)

        # Merge saved data and options so existing values are pre-filled.
        defaults = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(defaults),
            errors=errors,
        )
