"""Sensor platform for Simple Smart Cover integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Simple Smart Cover sensors."""
    async_add_entities(
        [
            SimpleSmartCoverTargetPositionSensor(hass, config_entry),
            SimpleSmartCoverDecisionSensor(hass, config_entry),
        ]
    )


class SimpleSmartCoverTargetPositionSensor(SensorEntity):
    """Sensor showing the target position."""

    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._attr_name = f"{config_entry.data['name']} Zielposition"
        self._attr_unique_id = f"{config_entry.entry_id}_target_position"
        self._cover_entity_id = f"cover.{config_entry.data['name'].lower().replace(' ', '_')}"

    async def async_added_to_hass(self) -> None:
        """Register state change listener."""
        await super().async_added_to_hass()

        @callback
        def _async_state_changed(event):
            """Handle cover state change."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            self._attr_native_value = new_state.attributes.get("target_position")
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._cover_entity_id, _async_state_changed
            )
        )


class SimpleSmartCoverDecisionSensor(SensorEntity):
    """Sensor showing the decision reason."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._attr_name = f"{config_entry.data['name']} Entscheidung"
        self._attr_unique_id = f"{config_entry.entry_id}_decision"
        self._cover_entity_id = f"cover.{config_entry.data['name'].lower().replace(' ', '_')}"

    async def async_added_to_hass(self) -> None:
        """Register state change listener."""
        await super().async_added_to_hass()

        @callback
        def _async_state_changed(event):
            """Handle cover state change."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            self._attr_native_value = new_state.attributes.get("decision_reason")
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._cover_entity_id, _async_state_changed
            )
        )
