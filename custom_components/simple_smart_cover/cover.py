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

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COVERS,
    CONF_ENABLE_MANUAL_ACTIVITY_PAUSE,
    CONF_ENABLE_QUIET_MODE,
    CONF_MANUAL_ACTIVITY_DURATION,
    CONF_MIN_POSITION_CHANGE,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_TEST_MODE,
    DEFAULT_MANUAL_ACTIVITY_DURATION,
    DEFAULT_MIN_POSITION_CHANGE,
    DOMAIN,
)
from .decision import DecisionContext, DecisionEngine
from .entities import SimpleSmartCoverDeviceMixin

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the virtual cover entity for the config entry."""
    async_add_entities([SimpleSmartCoverEntity(hass, config_entry)])


class SimpleSmartCoverEntity(SimpleSmartCoverDeviceMixin, CoverEntity):
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
        """Publish the entity reference and register listeners."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN][self._entry_id]["cover"] = self
        self.async_on_remove(
            self._config_entry.add_update_listener(self._async_update_options)
        )
        self._register_cover_state_listener()
        self.async_on_remove(self._unregister_cover_state_listener)

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

    async def _async_update_options(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle options changes: re-register listeners, rebuild triggers, recalculate."""
        self._register_cover_state_listener()

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

    def get_pause_remaining_minutes(self) -> int | None:
        """Return remaining pause minutes, or None if not paused."""
        if not self.is_manual_pause_active():
            return None
        remaining = self._manual_pause_until - dt_util.now()
        return max(0, int(remaining.total_seconds() // 60))

    def reset_manual_pause(self) -> None:
        """Reset the manual activity pause immediately."""
        self._manual_pause_until = None
        _LOGGER.debug("Manual activity pause reset for %s", self._config_entry.title)
        self.async_write_ha_state()

    def _refresh_manual_pause_state(self) -> bool:
        """Clear an expired pause. Return True if the pause is still active."""
        if not self._data.get(CONF_ENABLE_MANUAL_ACTIVITY_PAUSE, False):
            self._manual_pause_until = None
            return False

        if self._manual_pause_until is None:
            return False

        if dt_util.now() < self._manual_pause_until:
            return True

        self._manual_pause_until = None
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
        """Return entity-specific state attributes."""
        return {
            "decision_reason": self._decision_reason,
            "decision_details": self._decision_details,
            "should_move": self._should_move,
            "target_position": self._target_position,
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
            ctx = self._engine.build_context(is_evening=False)
        new_position = self._engine.target_position(ctx)
        self._target_position = new_position
        self._decision_reason = self._engine.reason(ctx)
        self._decision_details = self._engine.details(ctx)

        # Only move when the real covers differ enough from the target.
        self._should_move = self._compute_should_move(new_position)
        self.async_write_ha_state()

        if self._should_move and not self._data.get(CONF_TEST_MODE, False):
            await self._dispatch_to_covers(new_position)

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
