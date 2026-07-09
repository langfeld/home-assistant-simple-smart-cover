"""Sensor platform for Simple Smart Cover integration.

Four sensors per cover group:
- Target position (mirrors the cover's target_position attribute).
- Decision reason (mirrors decision_reason + decision_details).
- Pause active (binary sensor, live from the cover entity).
- Pause remaining (minutes, live from the cover entity).

The first two track cover state changes via SimpleSmartCoverStateSensorMixin;
the pause sensors use SimpleSmartCoverPauseEntityMixin which adds a periodic
refresh so expired pauses clear without a cover state change.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SUFFIX_DECISION,
    SUFFIX_PAUSE_ACTIVE,
    SUFFIX_PAUSE_REMAINING,
    SUFFIX_TARGET_POSITION,
)
from .entities import (
    SimpleSmartCoverPauseEntityMixin,
    SimpleSmartCoverStateSensorMixin,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the four sensors for the config entry."""
    async_add_entities(
        [
            SimpleSmartCoverTargetPositionSensor(hass, config_entry),
            SimpleSmartCoverDecisionSensor(hass, config_entry),
            SimpleSmartCoverPauseSensor(hass, config_entry),
            SimpleSmartCoverPauseRemainingSensor(hass, config_entry),
        ]
    )


class SimpleSmartCoverTargetPositionSensor(SimpleSmartCoverStateSensorMixin, SensorEntity):
    """Sensor showing the computed target position in percent."""

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the target position sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_target_position"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} {SUFFIX_TARGET_POSITION}"

    def _update_from_cover_state(self, state) -> None:
        """Read the target_position attribute from the cover state."""
        if state is None:
            return
        self._attr_native_value = state.attributes.get("target_position")


class SimpleSmartCoverDecisionSensor(SimpleSmartCoverStateSensorMixin, SensorEntity):
    """Diagnostic sensor showing the decision reason and details."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the decision sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_decision"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} {SUFFIX_DECISION}"

    def _update_from_cover_state(self, state) -> None:
        """Read decision_reason and decision_details from the cover state."""
        if state is None:
            return
        self._attr_native_value = state.attributes.get("decision_reason")
        self._attr_extra_state_attributes = state.attributes.get("decision_details")


class SimpleSmartCoverPauseSensor(SimpleSmartCoverPauseEntityMixin, BinarySensorEntity):
    """Binary sensor showing whether the manual activity pause is active."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the pause binary sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_pause_active"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} {SUFFIX_PAUSE_ACTIVE}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the manual activity pause is currently active."""
        cover = self._get_cover_entity()
        if cover is None:
            return None
        return cover.is_manual_pause_active()


class SimpleSmartCoverPauseRemainingSensor(SimpleSmartCoverPauseEntityMixin, SensorEntity):
    """Sensor showing the remaining manual activity pause minutes."""

    _attr_native_unit_of_measurement = "min"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the remaining-minutes sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_pause_remaining"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} {SUFFIX_PAUSE_REMAINING}"

    @property
    def native_value(self) -> int | None:
        """Return remaining pause minutes, or None if not paused."""
        cover = self._get_cover_entity()
        if cover is None:
            return None
        return cover.get_pause_remaining_minutes()
