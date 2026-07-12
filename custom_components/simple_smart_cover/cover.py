"""Cover platform for Simple Smart Cover integration.

The cover entity is the brain of a cover group: it owns the target position,
decides when to move the real covers and tracks the manual-activity pause.
The actual decision logic (sun angle, weather, temperature, thresholds) lives
in ``decision.py``; this module orchestrates evaluation, pause handling and
command dispatch.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

import voluptuous as vol

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COVERS,
    CONF_ENABLE_MANUAL_ACTIVITY_PAUSE,
    CONF_ENABLE_QUIET_MODE,
    CONF_MANUAL_ACTIVITY_DURATION,
    CONF_MIN_POSITION_CHANGE,
    CONF_MIN_SUN_ELEVATION,
    CONF_POSITION_CLOUDY,
    CONF_POSITION_EVENING,
    CONF_POSITION_SUNNY_IN_ANGLE,
    CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
    CONF_PRESENCE_PAUSE_EXTENSION,
    CONF_PRESENCE_SENSOR,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_SUN_ANGLE_TOLERANCE,
    CONF_TEST_MODE,
    CONF_USE_FORECAST_MAX_TEMP,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_ORIENTATION,
    DEFAULT_MANUAL_ACTIVITY_DURATION,
    DEFAULT_MIN_POSITION_CHANGE,
    DEFAULT_MIN_SUN_ELEVATION,
    DEFAULT_POSITION_CLOUDY,
    DEFAULT_POSITION_EVENING,
    DEFAULT_POSITION_SUNNY_IN_ANGLE,
    DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE,
    DEFAULT_PRESENCE_PAUSE_EXTENSION,
    DEFAULT_SUN_ANGLE_TOLERANCE,
    DEFAULT_WINDOW_ORIENTATION,
    DOMAIN,
    SERVICE_SET_POSITIONS,
)
from .decision import DecisionContext, DecisionEngine, ForecastData
from .entities import SimpleSmartCoverDeviceMixin

_LOGGER = logging.getLogger(__name__)

# Voluptuous schema for the set_positions entity service. Each field is
# optional; only the provided values are written to the config entry options.
_SET_POSITIONS_SCHEMA = {
    vol.Optional(CONF_POSITION_SUNNY_IN_ANGLE): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(CONF_POSITION_SUNNY_OUTSIDE_ANGLE): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
    vol.Optional(CONF_POSITION_CLOUDY): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=100)
    ),
}

# Grace period after our own service call during which cover state changes are
# treated as our own movement rather than a manual intervention.
_OWN_COMMAND_GRACE = timedelta(seconds=120)
# Maximum window after our own command during which a position-match fallback
# is used to identify our own movement for slow covers. After this window the
# entry is cleared so manual movements are always detected, even if they end
# up at the same position the automation previously requested.
_OWN_COMMAND_WINDOW = timedelta(minutes=10)
# Position tolerance (percent) within which a cover is considered to match the
# position we requested.
_OWN_POSITION_TOLERANCE = 3
# Ignore cover state changes shortly after startup so HA state restoration does
# not trigger a false manual-pause.
_STARTUP_QUIET = timedelta(seconds=60)

# Maximum time difference between the sun-in-window time and the closest
# forecast entry. If the closest entry is further away than this, the forecast
# is considered not usable and we fall back to the configured temp_forecast_entity.
_MAX_FORECAST_TIME_DIFF = timedelta(hours=2)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the virtual cover entity for the config entry."""
    async_add_entities([SimpleSmartCoverEntity(hass, config_entry)])

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_POSITIONS,
        _SET_POSITIONS_SCHEMA,
        "async_set_positions",
    )


class SimpleSmartCoverEntity(SimpleSmartCoverDeviceMixin, RestoreEntity, CoverEntity):
    """Virtual cover entity representing one cover group and its automation."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize state and the decision engine."""
        self.hass = hass
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._attr_unique_id = f"{config_entry.entry_id}_cover"

        # Target position and decision output exposed to sensors.
        self._target_position = 100
        self._decision_reason = "unknown"
        self._decision_details: dict[str, Any] = {}
        self._should_move = False

        # Manual-activity pause tracking.
        self._manual_pause_until: datetime | None = None

        # Presence-based pause extension. Presence alone does not start a
        # pause; it only holds (sticky) and extends (nachlauf) an existing
        # manual pause so the automation does not fight the user while a
        # room is occupied.
        self._presence_active: bool = False
        self._presence_off_at: datetime | None = None
        self._unsub_presence: Callable[[], None] | None = None

        # Evening state is persisted so re-evaluation intervals do not switch
        # back to daytime logic after sunset.
        self._force_evening = False

        self._startup_time = dt_util.now()
        self._unsub_cover_state: Callable[[], None] | None = None

        # Records (sent_time, sent_position) per cover to distinguish our own
        # commands from manual movements.
        self._last_sent_positions: dict[str, tuple[datetime, int]] = {}

        # The engine reads the live merged config via the lambda so option
        # changes take effect without rebuilding the engine.
        self._engine = DecisionEngine(
            hass, lambda: self._data, config_entry.title
        )

    # -- config access -----------------------------------------------------

    @property
    def _data(self) -> dict[str, Any]:
        """Return merged config entry data and options."""
        return {**self._config_entry.data, **self._config_entry.options}

    # -- lifecycle ---------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Publish the entity reference and register listeners.

        In-memory state (manual pause, presence nachlauf, evening mode) is
        restored from the last state before the HA restart so manually set
        pauses survive a restart.
        """
        await super().async_added_to_hass()

        # Restore state that was persisted in extra_state_attributes before
        # the restart. Without this, manual pauses and presence locks would
        # be lost every time HA restarts.
        if (last_state := await self.async_get_last_state()) is not None:
            self._restore_from_last_state(last_state)

        self.hass.data[DOMAIN][self._entry_id]["cover"] = self
        self.async_on_remove(
            self._config_entry.add_update_listener(self._async_update_options)
        )
        self._register_cover_state_listener()
        self.async_on_remove(self._unregister_cover_state_listener)
        self._register_presence_listener()
        self.async_on_remove(self._unregister_presence_listener)

    def _restore_from_last_state(self, last_state) -> None:
        """Restore in-memory state from the last state before restart.

        Only restores values that are still valid (e.g. a pause that has not
        expired). Expired values are silently dropped so the cover starts
        fresh after a long downtime.
        """
        attrs = last_state.attributes
        now = dt_util.now()

        # Manual pause timer
        pause_until_raw = attrs.get("manual_pause_until")
        if pause_until_raw:
            restored = dt_util.parse_datetime(pause_until_raw)
            if restored is not None and now < restored:
                self._manual_pause_until = restored
                _LOGGER.debug(
                    "Restored manual pause until %s for %s",
                    restored,
                    self._config_entry.title,
                )

        # Presence nachlauf window
        presence_off_raw = attrs.get("presence_off_at")
        if presence_off_raw:
            restored = dt_util.parse_datetime(presence_off_raw)
            if restored is not None and now < restored + timedelta(hours=12):
                self._presence_off_at = restored
                _LOGGER.debug(
                    "Restored presence off_at %s for %s",
                    restored,
                    self._config_entry.title,
                )

        # Evening mode
        if attrs.get("force_evening"):
            self._force_evening = True
            _LOGGER.debug(
                "Restored evening mode for %s", self._config_entry.title
            )

    def _register_cover_state_listener(self) -> None:
        """Register or re-register the real-cover state-change listener."""
        if self._unsub_cover_state is not None:
            self._unsub_cover_state()
            self._unsub_cover_state = None
        covers = self._data.get(CONF_COVERS, [])
        if covers:
            self._unsub_cover_state = async_track_state_change_event(
                self.hass, covers, self._async_cover_state_changed
            )

    def _unregister_cover_state_listener(self) -> None:
        """Unsubscribe the real-cover state-change listener."""
        if self._unsub_cover_state is not None:
            self._unsub_cover_state()
            self._unsub_cover_state = None

    def _register_presence_listener(self) -> None:
        """Register or re-register the presence-sensor state listener.

        When no presence sensor is configured the presence state is reset to
        defaults so a previously configured sensor does not keep the pause
        sticky after the user cleared the field.
        """
        if self._unsub_presence is not None:
            self._unsub_presence()
            self._unsub_presence = None

        presence_sensor = self._data.get(CONF_PRESENCE_SENSOR)
        if not presence_sensor:
            self._presence_active = False
            self._presence_off_at = None
            return

        # Seed the initial presence state from the current entity state so the
        # sticky/nachlauf logic works before the first state change arrives.
        # Only clear the nachlauf window when the sensor is currently on; if
        # it is off we keep a restored _presence_off_at so the nachlauf
        # survives a restart.
        state = self.hass.states.get(presence_sensor)
        self._presence_active = bool(state is not None and state.state == "on")
        if self._presence_active:
            self._presence_off_at = None

        self._unsub_presence = async_track_state_change_event(
            self.hass, [presence_sensor], self._async_presence_state_changed
        )

    def _unregister_presence_listener(self) -> None:
        """Unsubscribe the presence-sensor state-change listener."""
        if self._unsub_presence is not None:
            self._unsub_presence()
            self._unsub_presence = None

    @callback
    def _async_presence_state_changed(self, event) -> None:
        """Track presence-sensor transitions and refresh the pause state.

        ``on`` marks the room as occupied and clears any nachlauf window
        (sticky mode). Any other state (``off``, ``unavailable``,
        ``unknown``) is treated as not present (fail-open) and starts the
        nachlauf window from the transition time so short absences (e.g.
        grabbing something from the kitchen) do not let the automation
        intervene.
        """
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state == "on":
            self._presence_active = True
            self._presence_off_at = None
        else:
            # Only start the nachlauf window on an actual on->off transition
            # so a sensor that reports off repeatedly does not reset it.
            if self._presence_active:
                self._presence_off_at = dt_util.now()
            self._presence_active = False

        _LOGGER.debug(
            "Presence sensor for %s changed to %s (active=%s, off_at=%s)",
            self._config_entry.title,
            new_state.state,
            self._presence_active,
            self._presence_off_at,
        )
        self.async_write_ha_state()

    async def _async_update_options(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle options changes: re-register listeners, rebuild triggers, recalculate."""
        self._register_cover_state_listener()
        self._register_presence_listener()

        from .trigger import async_setup_triggers

        entry_data = hass.data.get(DOMAIN, {}).get(self._entry_id, {})
        for remove_callback in entry_data.get("trigger_removals", []):
            remove_callback()
        entry_data["trigger_removals"] = []
        await async_setup_triggers(hass, config_entry, self)

        await self.async_update_position()

    # -- manual activity pause detection ----------------------------------

    @staticmethod
    def _is_movement_toward_target(event, sent_pos: int) -> bool:
        """Return True if the cover is moving toward our requested position.

        Compares the old and new positions from the state-change event against
        the position we requested. If the new position is closer to the target
        (within tolerance) the movement is ours. If the cover reversed
        direction and moves away from the target, it is a manual override and
        the method returns False. When positions cannot be determined the
        method defaults to True (assume our own movement) to avoid false
        positives during normal cover operation.
        """
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if old_state is None or new_state is None:
            return True
        try:
            old_pos = int(old_state.attributes.get("current_position", -1))
            new_pos = int(new_state.attributes.get("current_position", -1))
        except (ValueError, TypeError):
            return True
        if old_pos < 0 or new_pos < 0:
            return True
        old_dist = abs(old_pos - sent_pos)
        new_dist = abs(new_pos - sent_pos)
        return new_dist <= old_dist + _OWN_POSITION_TOLERANCE

    @callback
    def _async_cover_state_changed(self, event) -> None:
        """Detect manual or external cover movements and start a pause.

        A state change is considered our own movement (and therefore ignored)
        when it happens within the grace period after we sent a command and the
        cover is moving toward the position we requested. A direction reversal
        during the grace period (the cover moves away from our requested
        position) is detected as a manual override. After the grace period a
        position match within the command window is still treated as our own
        movement (fallback for slow covers). Everything else is treated as a
        manual intervention and starts the pause timer.
        """
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            return

        new_state = event.data.get("new_state")
        if new_state is None:
            return

        now = dt_util.now()
        # Ignore state changes shortly after startup while HA restores states.
        if now < self._startup_time + _STARTUP_QUIET:
            return

        entity_id = new_state.entity_id
        last_sent = self._last_sent_positions.get(entity_id)

        if last_sent is not None:
            sent_time, sent_pos = last_sent
            if now < sent_time + _OWN_COMMAND_GRACE:
                # Movement shortly after our own command. Usually this is the
                # cover responding to our command, but a direction reversal
                # (moving away from the requested position) is a manual
                # override and must start the pause.
                if self._is_movement_toward_target(event, sent_pos):
                    return
            elif now < sent_time + _OWN_COMMAND_WINDOW:
                # After grace but within the command window: a position match
                # is still considered our own movement (fallback for slow
                # covers that take longer than the grace period to finish).
                try:
                    current_pos = int(new_state.attributes.get("current_position", -1))
                    if (
                        current_pos >= 0
                        and abs(current_pos - sent_pos) <= _OWN_POSITION_TOLERANCE
                    ):
                        # Position matches what we requested: not a manual move.
                        return
                except (ValueError, TypeError):
                    pass
            else:
                # Window expired: clear the stale entry so future movements
                # are correctly detected as manual even if they end up at the
                # same position the automation previously requested.
                self._last_sent_positions.pop(entity_id, None)

        # Movement was not initiated by us: start the manual activity pause.
        duration_minutes = self._data.get(
            CONF_MANUAL_ACTIVITY_DURATION, DEFAULT_MANUAL_ACTIVITY_DURATION
        )
        self._manual_pause_until = now + timedelta(minutes=duration_minutes)
        _LOGGER.debug(
            "Manual activity detected on %s, pausing automation until %s",
            entity_id,
            self._manual_pause_until,
        )
        # Notify dependent sensors (pause binary sensor, remaining minutes).
        self.async_write_ha_state()

    # -- pause public API --------------------------------------------------

    def set_evening_state(self, is_evening: bool) -> None:
        """Force evening mode on or off (used by the sunset trigger)."""
        self._force_evening = is_evening

    def is_manual_pause_active(self) -> bool:
        """Return whether the manual activity pause is currently active."""
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            return False
        return self._refresh_manual_pause_state()

    def is_presence_lock_active(self) -> bool:
        """Return True if the pause is currently held by presence.

        Presence alone never starts a pause; this is only True when a manual
        pause exists AND the configured presence sensor is either currently
        ``on`` (sticky) or within the nachlauf window after it turned off.
        """
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            return False
        if self._manual_pause_until is None:
            return False
        if not self._data.get(CONF_PRESENCE_SENSOR):
            return False
        if self._presence_active:
            return True
        if self._presence_off_at is None:
            return False
        extension = timedelta(
            minutes=self._data.get(
                CONF_PRESENCE_PAUSE_EXTENSION, DEFAULT_PRESENCE_PAUSE_EXTENSION
            )
        )
        return dt_util.now() < self._presence_off_at + extension

    def get_pause_remaining_minutes(self) -> int | None:
        """Return remaining pause minutes, or None if not paused.

        While presence holds the pause sticky, the configured nachlauf value
        is reported (the time the pause would still run if the user left
        now). During the nachlauf window the value counts down from the
        off-transition + extension. Otherwise the manual-pause timer counts
        down as before.
        """
        if not self.is_manual_pause_active():
            return None

        now = dt_util.now()
        has_presence_sensor = bool(self._data.get(CONF_PRESENCE_SENSOR))

        if has_presence_sensor and self._presence_active:
            # Sticky: report the nachlauf value that would apply on leave.
            return int(
                self._data.get(
                    CONF_PRESENCE_PAUSE_EXTENSION, DEFAULT_PRESENCE_PAUSE_EXTENSION
                )
            )

        if has_presence_sensor and self._presence_off_at is not None:
            extension = timedelta(
                minutes=self._data.get(
                    CONF_PRESENCE_PAUSE_EXTENSION, DEFAULT_PRESENCE_PAUSE_EXTENSION
                )
            )
            remaining = (self._presence_off_at + extension) - now
            return max(0, int(remaining.total_seconds() // 60))

        remaining = self._manual_pause_until - now
        return max(0, int(remaining.total_seconds() // 60))

    def reset_manual_pause(self) -> None:
        """Reset the manual activity pause immediately.

        Clears both the manual pause timer and the presence nachlauf window so
        the reset takes precedence over an active presence lock. The live
        ``_presence_active`` flag is intentionally left untouched because it
        mirrors the sensor state; without ``_manual_pause_until`` the
        presence lock has no effect.
        """
        self._manual_pause_until = None
        self._presence_off_at = None
        _LOGGER.debug("Manual activity pause reset for %s", self._config_entry.title)
        self.async_write_ha_state()

    def _refresh_manual_pause_state(self) -> bool:
        """Clear an expired pause. Return True if the pause is still active.

        Evaluation order when a presence sensor is configured:
        1. No manual pause recorded -> not paused (presence alone does not
           start a pause, only extends an existing one).
        2. Presence ``on`` -> sticky, pause stays active regardless of the
           manual timer.
        3. Within the nachlauf window after presence turned off -> active.
        4. Manual pause timer not yet expired -> active.
        5. Everything expired -> clear and return False.
        """
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            self._manual_pause_until = None
            self._presence_off_at = None
            return False

        if self._manual_pause_until is None:
            # Nothing to extend; drop a stale nachlauf window if any.
            self._presence_off_at = None
            return False

        now = dt_util.now()
        presence_sensor = self._data.get(CONF_PRESENCE_SENSOR)

        if presence_sensor:
            if self._presence_active:
                return True
            extension = timedelta(
                minutes=self._data.get(
                    CONF_PRESENCE_PAUSE_EXTENSION, DEFAULT_PRESENCE_PAUSE_EXTENSION
                )
            )
            if (
                self._presence_off_at is not None
                and now < self._presence_off_at + extension
            ):
                return True
            # Nachlauf expired: clear it so the manual timer can expire below.
            self._presence_off_at = None

        if now < self._manual_pause_until:
            return True

        self._manual_pause_until = None
        self._presence_off_at = None
        return False

    # -- quiet time --------------------------------------------------------

    def _is_quiet_time(self) -> bool:
        """Check if the current time is inside the configured quiet window.

        Supports overnight windows where the start time is later than the end
        time (e.g. 22:00 - 07:00).
        """
        if not self._data.get(CONF_ENABLE_QUIET_MODE, False):
            return False

        now_str = dt_util.now().strftime("%H:%M:%S")
        quiet_start = self._data.get(CONF_QUIET_START, "22:00:00")
        quiet_end = self._data.get(CONF_QUIET_END, "07:00:00")

        if quiet_start <= quiet_end:
            return quiet_start <= now_str <= quiet_end
        return now_str >= quiet_start or now_str <= quiet_end

    # -- cover entity interface -------------------------------------------

    @property
    def current_cover_position(self) -> int:
        """Return the current (target) cover position."""
        return self._target_position

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity-specific state attributes.

        Includes the manual pause timer and evening flag so they survive a
        HA restart via RestoreEntity. The configured target positions are
        exposed so the custom card (and other consumers) can read and display
        them without accessing the config entry directly.
        """
        return {
            "decision_reason": self._decision_reason,
            "decision_details": self._decision_details,
            "should_move": self._should_move,
            "target_position": self._target_position,
            "position_sunny_in_angle": self._data.get(
                CONF_POSITION_SUNNY_IN_ANGLE, DEFAULT_POSITION_SUNNY_IN_ANGLE
            ),
            "position_sunny_outside_angle": self._data.get(
                CONF_POSITION_SUNNY_OUTSIDE_ANGLE, DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE
            ),
            "position_cloudy": self._data.get(
                CONF_POSITION_CLOUDY, DEFAULT_POSITION_CLOUDY
            ),
            "position_evening": self._data.get(
                CONF_POSITION_EVENING, DEFAULT_POSITION_EVENING
            ),
            "manual_pause_until": (
                self._manual_pause_until.isoformat()
                if self._manual_pause_until
                else None
            ),
            "force_evening": self._force_evening,
            "presence_active": self._presence_active,
            "presence_lock_active": self.is_presence_lock_active(),
            "presence_off_at": (
                self._presence_off_at.isoformat() if self._presence_off_at else None
            ),
        }

    @property
    def is_closed(self) -> bool:
        """Return True if the cover is fully closed."""
        return self._target_position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (set target position to 100)."""
        await self.async_set_cover_position(position=100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (set target position to 0)."""
        await self.async_set_cover_position(position=0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the target position from a service call."""
        position = kwargs.get("position", 100)
        self._target_position = int(position)
        self.async_write_ha_state()

    async def async_set_positions(self, **kwargs: Any) -> None:
        """Update configured target positions from a service call.

        Merges the provided values into the config entry options. The existing
        update listener re-registers listeners and re-evaluates the position
        automatically, so no explicit recalculation is needed here.
        """
        new_options = dict(self._config_entry.options)
        updated = False
        for key in (
            CONF_POSITION_SUNNY_IN_ANGLE,
            CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
            CONF_POSITION_CLOUDY,
        ):
            value = kwargs.get(key)
            if value is not None:
                new_options[key] = int(value)
                updated = True
        if updated:
            self.hass.config_entries.async_update_entry(
                self._config_entry, options=new_options
            )

    # -- core evaluation ---------------------------------------------------

    async def async_update_position(self, is_evening: bool | None = None) -> None:
        """Re-evaluate the target position and move the covers if needed.

        Evaluation order:
        1. Evening override (persisted so re-evaluations stay in evening mode).
        2. Quiet time -> no movement.
        3. Manual activity pause -> no movement.
        4. Weather unavailable (daytime only) -> no movement.
        5. Normal decision via the DecisionEngine.
        """
        if is_evening is not None:
            self._force_evening = is_evening
        is_evening = self._force_evening

        # Quiet time: never move, but still publish diagnostic details.
        if self._is_quiet_time():
            ctx = self._engine.build_context(is_evening=is_evening, is_cloudy=False)
            self._set_decision("quiet_time", ctx, move=False)
            return

        # Manual activity pause: respect the user's manual movement.
        if self._refresh_manual_pause_state():
            ctx = self._engine.build_context(is_evening=is_evening, is_cloudy=False)
            self._set_decision("manual_activity_pause", ctx, move=False)
            return

        # Daytime decisions need a working weather entity.
        if not is_evening and not self._engine.is_weather_available():
            ctx = self._engine.build_context(is_evening=is_evening, is_cloudy=False)
            self._set_decision("weather_unavailable", ctx, move=False)
            return

        # Normal decision path: build context once, derive all outputs from it.
        # Evening decisions force is_cloudy=False in the diagnostic details to
        # match the original behaviour (evening ignores weather conditions).
        if is_evening:
            ctx = self._engine.build_context(is_evening=True, is_cloudy=False)
        else:
            forecast_data = None
            if self._data.get(CONF_USE_FORECAST_MAX_TEMP, False):
                forecast_data = await self._build_forecast_data()
            ctx = self._engine.build_context(
                is_evening=False, forecast_data=forecast_data
            )
        new_position = self._engine.target_position(ctx)
        self._target_position = new_position
        self._decision_reason = self._engine.reason(ctx)
        self._decision_details = self._engine.details(ctx)

        # Only move when the real covers differ enough from the target.
        self._should_move = self._compute_should_move(new_position)
        self.async_write_ha_state()

        if self._should_move and not self._data.get(CONF_TEST_MODE, False):
            await self._dispatch_to_covers(new_position)

    # -- forecast-based preemptive decision --------------------------------

    async def _build_forecast_data(self) -> ForecastData | None:
        """Calculate sun-in-window time and fetch forecast at that time.

        Returns a ForecastData with the forecast temperature and condition at
        the calculated sun-in-window time. Falls back to the configured
        temp_forecast_entity (day's max) and current weather condition if the
        forecast at the sun-in-window time cannot be determined.

        Returns None if the sun calculation itself fails, so the caller falls
        back to the reactive (current-position) decision path.
        """
        from .sun_calc import get_sun_in_window_time

        data = self._data
        orientation = data.get(
            CONF_WINDOW_ORIENTATION, DEFAULT_WINDOW_ORIENTATION
        )
        tolerance = data.get(
            CONF_SUN_ANGLE_TOLERANCE, DEFAULT_SUN_ANGLE_TOLERANCE
        )
        min_elevation = data.get(
            CONF_MIN_SUN_ELEVATION, DEFAULT_MIN_SUN_ELEVATION
        )

        try:
            sun_in_window_time = get_sun_in_window_time(
                self.hass, orientation, tolerance, min_elevation
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Sun-in-window calculation failed for %s: %s, "
                "falling back to reactive mode",
                self._config_entry.title,
                exc,
            )
            return None

        if sun_in_window_time is None:
            # Sun will not reach the window today. Still build forecast data
            # with sun_in_window_time=None so is_sunny_in_angle is False.
            temperature = self._engine.get_temperature()
            condition = self._engine.get_weather_condition()
            return ForecastData(
                temperature=temperature,
                condition=condition,
                sun_in_window_time=None,
            )

        # Try to get the hourly forecast at the sun-in-window time.
        weather_entity = data.get(CONF_WEATHER_ENTITY)
        if weather_entity:
            entry = await self._get_forecast_at_time(
                weather_entity, sun_in_window_time
            )
            if entry is not None:
                temp = entry.get("temperature")
                condition = entry.get("condition")
                if temp is not None:
                    return ForecastData(
                        temperature=float(temp),
                        condition=condition or "unknown",
                        sun_in_window_time=sun_in_window_time,
                    )

        # Fallback: use temp_forecast_entity (day's max) and current condition.
        _LOGGER.info(
            "Forecast at sun-in-window time %s unavailable for %s, "
            "falling back to daily max temperature",
            sun_in_window_time,
            self._config_entry.title,
        )
        temperature = self._engine.get_temperature()
        condition = self._engine.get_weather_condition()
        return ForecastData(
            temperature=temperature,
            condition=condition,
            sun_in_window_time=sun_in_window_time,
        )

    async def _get_forecast_at_time(
        self, weather_entity: str, target_time: datetime
    ) -> dict[str, Any] | None:
        """Fetch the hourly weather forecast and find the closest entry.

        Returns None if no forecast is available or the closest entry is
        further away than _MAX_FORECAST_TIME_DIFF from target_time.
        """
        forecast = await self._fetch_weather_forecast(weather_entity)
        if not forecast:
            return None

        closest: dict[str, Any] | None = None
        closest_diff: timedelta | None = None

        for entry in forecast:
            dt = entry.get("datetime")
            if dt is None:
                continue
            if isinstance(dt, str):
                dt = dt_util.parse_datetime(dt)
            if dt is None:
                continue
            diff = abs(dt - target_time)
            if closest_diff is None or diff < closest_diff:
                closest = entry
                closest_diff = diff

        if closest is None or closest_diff is None:
            return None
        if closest_diff > _MAX_FORECAST_TIME_DIFF:
            _LOGGER.debug(
                "Closest forecast entry is %s away from sun-in-window time, "
                "considered too far",
                closest_diff,
            )
            return None
        return closest

    async def _fetch_weather_forecast(self, weather_entity: str) -> list | None:
        """Get the hourly forecast from a weather entity.

        Tries the ``forecast`` state attribute first (older HA versions) and
        falls back to the ``weather.get_forecast`` service (HA 2024.2+).
        """
        # Try the forecast attribute first (works in all HA versions that
        # still populate it; no service call overhead).
        state = self.hass.states.get(weather_entity)
        if state is not None:
            forecast = state.attributes.get("forecast")
            if forecast:
                return forecast

        # Fall back to the weather.get_forecast service (HA 2024.2+).
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecast",
                {"entity_id": weather_entity, "type": "hourly"},
                return_response=True,
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Could not fetch weather forecast for %s: %s", weather_entity, exc
            )
            return None

        if not isinstance(response, dict):
            return None

        # Response shape: {entity_id: {"forecast": [...]}}
        entity_response = response.get(weather_entity)
        if isinstance(entity_response, dict):
            return entity_response.get("forecast", [])

        # Some HA versions may return a flat {"forecast": [...]} dict.
        if "forecast" in response:
            return response["forecast"]

        return None

    def _set_decision(self, reason: str, ctx: DecisionContext, *, move: bool) -> None:
        """Record a non-normal decision (quiet/pause/unavailable) and publish state."""
        self._decision_reason = reason
        self._decision_details = self._engine.details(ctx)
        self._should_move = move
        self.async_write_ha_state()

    def _compute_should_move(self, new_position: int) -> bool:
        """Return True if the real covers differ enough from the target.

        Averages the current positions of all configured covers and compares
        against the configured minimum change threshold. If no cover reports a
        position, we assume a move is needed.
        """
        current_positions: list[int] = []
        for cover in self._data.get(CONF_COVERS, []):
            state = self.hass.states.get(cover)
            if state is None:
                continue
            try:
                pos = int(state.attributes.get("current_position", -1))
                if pos >= 0:
                    current_positions.append(pos)
            except (ValueError, TypeError):
                continue

        if not current_positions:
            return True

        avg_current = sum(current_positions) // len(current_positions)
        min_change = self._data.get(
            CONF_MIN_POSITION_CHANGE, DEFAULT_MIN_POSITION_CHANGE
        )
        return abs(new_position - avg_current) >= min_change

    async def _dispatch_to_covers(self, position: int) -> None:
        """Send the target position to every configured real cover.

        Records the sent time and position so the state-change listener can
        distinguish our own commands from manual movements.
        """
        now = dt_util.now()
        for cover in self._data.get(CONF_COVERS, []):
            await self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": cover, "position": position},
                blocking=False,
            )
            self._last_sent_positions[cover] = (now, position)
