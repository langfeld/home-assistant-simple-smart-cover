"""Button platform for Simple Smart Cover integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simple Smart Cover buttons."""
    async_add_entities(
        [
            SimpleSmartCoverPauseResetButton(hass, config_entry),
        ]
    )


class SimpleSmartCoverPauseResetButton(ButtonEntity):
    """Button to reset the manual activity pause."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the button."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_pause_reset"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} Pause zurücksetzen"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._config_entry.title,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

    def _get_cover(self):
        """Return the cover entity for this config entry."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if entry_data is None:
            return None
        return entry_data.get("cover")

    async def async_added_to_hass(self) -> None:
        """Register update listener so name changes are reflected."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._config_entry.add_update_listener(self._async_update_options)
        )

    async def _async_update_options(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle options update — refresh state to pick up name change."""
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Reset the manual activity pause."""
        cover = self._get_cover()
        if cover is not None:
            cover.reset_manual_pause()
