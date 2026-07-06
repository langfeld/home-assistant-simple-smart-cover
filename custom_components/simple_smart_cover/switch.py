"""Switch platform for Simple Smart Cover integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simple Smart Cover switches."""
    async_add_entities(
        [
            SimpleSmartCoverAutomationSwitch(hass, config_entry),
        ]
    )


class SimpleSmartCoverAutomationSwitch(SwitchEntity):
    """Switch to enable or disable automation for a cover group."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._attr_name = f"{config_entry.data['name']} Automatik"
        self._attr_unique_id = f"{config_entry.entry_id}_automation"
        self._is_on = True

    def _get_cover(self):
        """Return the cover entity for this config entry."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if entry_data is None:
            return None
        return entry_data.get("cover")

    async def async_added_to_hass(self) -> None:
        """Register the switch in hass data."""
        await super().async_added_to_hass()
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if entry_data is not None:
            entry_data["switch"] = self

    @property
    def is_on(self) -> bool:
        """Return true if automation is enabled."""
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automation."""
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automation."""
        self._is_on = False
        self.async_write_ha_state()
