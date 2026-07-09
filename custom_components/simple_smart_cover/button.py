"""Button platform for Simple Smart Cover integration.

A single config button per cover group that resets the manual activity pause
immediately, so the user does not have to wait for the pause timer to expire.

Entity names are translatable via ``_attr_translation_key`` and the ``entity``
section in the translation files.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entities import SimpleSmartCoverDeviceMixin


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the pause-reset button for the config entry."""
    async_add_entities([SimpleSmartCoverPauseResetButton(hass, config_entry)])


class SimpleSmartCoverPauseResetButton(SimpleSmartCoverDeviceMixin, ButtonEntity):
    """Button that resets the manual activity pause immediately."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_pause"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the pause-reset button."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_pause_reset"

    async def async_added_to_hass(self) -> None:
        """Register an update listener so name changes are reflected."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._config_entry.add_update_listener(self._async_update_options)
        )

    async def _async_update_options(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle options update - refresh state to pick up name changes."""
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Reset the manual activity pause on the cover entity."""
        cover = self._get_cover_entity()
        if cover is not None:
            cover.reset_manual_pause()
