"""Button platform for Simple Smart Cover integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the button."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._group_name = config_entry.data['name']
        self._attr_name = f"{config_entry.data['name']} Pause zurücksetzen"
        self._attr_unique_id = f"{config_entry.entry_id}_pause_reset"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._group_name,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

    def _get_cover(self):
        """Return the cover entity for this config entry."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if entry_data is None:
            return None
        return entry_data.get("cover")

    async def async_press(self) -> None:
        """Reset the manual activity pause."""
        cover = self._get_cover()
        if cover is not None:
            cover.reset_manual_pause()
