"""Sensor platform for Simple Smart Cover integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
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


class SimpleSmartCoverTargetPositionSensor(SensorEntity):
    """Sensor showing the target position."""

    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._group_name = config_entry.data['name']
        self._attr_name = f"{config_entry.data['name']} Zielposition"
        self._attr_unique_id = f"{config_entry.entry_id}_target_position"
        self._cover_entity_id = f"cover.{config_entry.data['name'].lower().replace(' ', '_')}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._group_name,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

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
        self._group_name = config_entry.data['name']
        self._attr_name = f"{config_entry.data['name']} Entscheidung"
        self._attr_unique_id = f"{config_entry.entry_id}_decision"
        self._cover_entity_id = f"cover.{config_entry.data['name'].lower().replace(' ', '_')}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._group_name,
            manufacturer="Simple Smart Cover",
            model="Cover Group",
        )

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
            self._attr_extra_state_attributes = new_state.attributes.get(
                "decision_details"
            )
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._cover_entity_id, _async_state_changed
            )
        )


class SimpleSmartCoverPauseSensor(BinarySensorEntity):
    """Binary sensor showing whether manual activity pause is active."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._group_name = config_entry.data['name']
        self._attr_name = f"{config_entry.data['name']} Pause aktiv"
        self._attr_unique_id = f"{config_entry.entry_id}_pause_active"
        self._cover_entity_id = f"cover.{config_entry.data['name'].lower().replace(' ', '_')}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._group_name,
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

        @callback
        def _async_state_changed(event):
            """Handle cover state change and update pause sensor."""
            cover = _get_cover_entity(self.hass, self._entry_id)
            if cover is not None:
                cover.update_pause_state()
            self.async_write_ha_state()

        cover = _get_cover_entity(self.hass, self._entry_id)
        covers = []
        if cover is not None:
            covers = cover._data.get("covers", [])

        if covers:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, covers, _async_state_changed
                )
            )

        # Also refresh periodically so the sensor turns off when pause expires.
        self.async_write_ha_state()


class SimpleSmartCoverPauseRemainingSensor(SensorEntity):
    """Sensor showing remaining manual activity pause minutes."""

    _attr_native_unit_of_measurement = "min"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry_id = config_entry.entry_id
        self._group_name = config_entry.data['name']
        self._attr_name = f"{config_entry.data['name']} Pause verbleibend"
        self._attr_unique_id = f"{config_entry.entry_id}_pause_remaining"
        self._cover_entity_id = f"cover.{config_entry.data['name'].lower().replace(' ', '_')}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover group."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._group_name,
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

        @callback
        def _async_state_changed(event):
            """Handle cover state change and update remaining pause sensor."""
            cover = _get_cover_entity(self.hass, self._entry_id)
            if cover is not None:
                cover.update_pause_state()
            self.async_write_ha_state()

        cover = _get_cover_entity(self.hass, self._entry_id)
        covers = []
        if cover is not None:
            covers = cover._data.get("covers", [])

        if covers:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, covers, _async_state_changed
                )
            )

        self.async_write_ha_state()
