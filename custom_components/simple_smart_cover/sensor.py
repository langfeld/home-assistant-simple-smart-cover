"""Sensor platform for Simple Smart Cover integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

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
            SimpleSmartCoverPauseSensor(hass, config_entry),
            SimpleSmartCoverPauseRemainingSensor(hass, config_entry),
        ]
    )


def _get_cover_entity(hass: HomeAssistant, entry_id: str):
    """Return the SimpleSmartCoverEntity for a config entry, if available."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
    if entry_data is None:
        return None
    return entry_data.get("cover")


def _get_cover_entity_id(hass: HomeAssistant, entry_id: str, title: str) -> str:
    """Return the virtual cover entity_id, falling back to slugified title."""
    entity_registry = er.async_get(hass)
    cover_entity_id = entity_registry.async_get_entity_id(
        "cover", DOMAIN, f"{entry_id}_cover"
    )
    if cover_entity_id is None:
        cover_entity_id = f"cover.{title.lower().replace(' ', '_')}"
    return cover_entity_id


class SimpleSmartCoverTargetPositionSensor(SensorEntity):
    """Sensor showing the target position."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_target_position"
        self._cover_entity_id: str | None = None

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} Zielposition"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._config_entry.title,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

    def _update_from_cover_state(self, state) -> None:
        """Update sensor value from a cover state object."""
        if state is None:
            return
        self._attr_native_value = state.attributes.get("target_position")

    async def async_added_to_hass(self) -> None:
        """Register state change listener."""
        await super().async_added_to_hass()

        self._cover_entity_id = _get_cover_entity_id(
            self.hass, self._entry_id, self._config_entry.title
        )

        # Set initial value from the cover's current state.
        self._update_from_cover_state(self.hass.states.get(self._cover_entity_id))

        @callback
        def _async_state_changed(event):
            """Handle cover state change."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            self._update_from_cover_state(new_state)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._cover_entity_id, _async_state_changed
            )
        )


class SimpleSmartCoverDecisionSensor(SensorEntity):
    """Sensor showing the decision reason."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_decision"
        self._cover_entity_id: str | None = None

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} Entscheidung"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._config_entry.title,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

    def _update_from_cover_state(self, state) -> None:
        """Update sensor value from a cover state object."""
        if state is None:
            return
        self._attr_native_value = state.attributes.get("decision_reason")
        self._attr_extra_state_attributes = state.attributes.get("decision_details")

    async def async_added_to_hass(self) -> None:
        """Register state change listener."""
        await super().async_added_to_hass()

        self._cover_entity_id = _get_cover_entity_id(
            self.hass, self._entry_id, self._config_entry.title
        )

        # Set initial value from the cover's current state.
        self._update_from_cover_state(self.hass.states.get(self._cover_entity_id))

        @callback
        def _async_state_changed(event):
            """Handle cover state change."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            self._update_from_cover_state(new_state)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._cover_entity_id, _async_state_changed
            )
        )


class SimpleSmartCoverPauseSensor(BinarySensorEntity):
    """Binary sensor showing whether manual activity pause is active."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_pause_active"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} Pause aktiv"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._config_entry.title,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if pause is active."""
        cover = _get_cover_entity(self.hass, self._entry_id)
        if cover is None:
            return None
        return cover.is_manual_pause_active()

    async def async_added_to_hass(self) -> None:
        """Register state change listeners."""
        await super().async_added_to_hass()

        cover_entity_id = _get_cover_entity_id(
            self.hass, self._entry_id, self._config_entry.title
        )

        @callback
        def _async_state_changed(event):
            """Handle virtual cover state change and update pause sensor."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, cover_entity_id, _async_state_changed
            )
        )

        # Periodic refresh so the sensor turns off when the pause expires.
        @callback
        def _async_periodic_update(now):
            """Periodically update the sensor state."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_interval(
                self.hass, _async_periodic_update, timedelta(minutes=1)
            )
        )

        self.async_write_ha_state()


class SimpleSmartCoverPauseRemainingSensor(SensorEntity):
    """Sensor showing remaining manual activity pause minutes."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "min"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_pause_remaining"

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return f"{self._config_entry.title} Pause verbleibend"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._config_entry.title,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

    @property
    def native_value(self) -> int | None:
        """Return remaining pause minutes."""
        cover = _get_cover_entity(self.hass, self._entry_id)
        if cover is None:
            return None
        return cover.get_pause_remaining_minutes()

    async def async_added_to_hass(self) -> None:
        """Register state change listeners."""
        await super().async_added_to_hass()

        cover_entity_id = _get_cover_entity_id(
            self.hass, self._entry_id, self._config_entry.title
        )

        @callback
        def _async_state_changed(event):
            """Handle virtual cover state change and update remaining pause sensor."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, cover_entity_id, _async_state_changed
            )
        )

        # Periodic refresh so the remaining minutes count down.
        @callback
        def _async_periodic_update(now):
            """Periodically update the sensor state."""
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_interval(
                self.hass, _async_periodic_update, timedelta(minutes=1)
            )
        )

        self.async_write_ha_state()
