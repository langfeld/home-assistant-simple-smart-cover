# Simple Smart Cover — Agent Notes

## Project Goal
Home Assistant custom integration that automates a group of covers (rollershutters/blinds) based on:
- Weather conditions
- Sun azimuth / elevation relative to window orientation
- Temperature (current or forecast high)
- Quiet time and manual-activity pause

One config entry = one cover group. The integration creates:
- A virtual `cover` entity representing the group target position
- A `sensor` for the target position
- A `sensor` for the decision reason
- A `binary_sensor` showing whether the manual activity pause is active
- A `sensor` showing the remaining pause minutes
- A `binary_sensor` showing whether the presence lock is active (optional, if a presence sensor is configured)
- A `button` to reset the manual activity pause immediately

No manual Helpers are required; values are exposed as native integration sensors.

## Repository Layout
```
home-assistant-simple-smart-cover/
├── custom_components/simple_smart_cover/
│   ├── __init__.py          # Entry setup/unload, migration of old config keys
│   ├── manifest.json        # Integration manifest
│   ├── const.py             # Config keys, defaults, label maps, migration map
│   ├── decision.py          # Decision engine (sun/weather/temp -> position/reason/details)
│   ├── entities.py          # Shared entity mixins + device-info / cover-lookup helpers
│   ├── schemas.py           # Voluptuous schema + selector builders for the config flow
│   ├── sun_calc.py          # Sun-in-window time calculation via astral (proactive forecast mode)
│   ├── cover.py             # Virtual cover entity + orchestration + pause handling
│   ├── sensor.py            # Target position, decision, pause, presence-lock sensors
│   ├── button.py            # Pause reset button
│   ├── trigger.py           # Time/sun-based re-evaluation triggers
│   └── translations/
│       ├── de.json          # German UI translations
│       └── en.json          # English UI translations (HA fallback)
├── hacs.json                # HACS metadata
├── .gitignore
├── README.md                # English README (primary)
└── README.de.md             # German README
```

## Domain
`simple_smart_cover`

## Key Design Decisions
- Config flow driven by `voluptuous` schemas.
- Options flow allows editing the entry afterwards.
- Config flow supports duplicating an existing group via `duplicate_select` / `duplicate_configure` steps.
- All entities of a config entry share the same `DeviceInfo`, so Home Assistant groups them into one device page per cover group.
- Optional entity selectors (e.g. temperature sensors) must be nulled on clear; use `null_cleared_optional_keys()` (from `schemas.py`) before saving.
- Cover entity reads `{**config_entry.data, **config_entry.options}` so option changes take effect immediately.
- Evening state is persisted on the cover entity (`_force_evening`) so re-evaluation intervals do not switch back to daytime logic after sunset.
- In-memory state (manual pause timer, presence nachlauf window, evening mode) is persisted via `extra_state_attributes` and restored on HA restart using `RestoreEntity`, so manually set pauses survive a restart.
- Manual activity pause is detected by listening to real cover state changes. Movements that occur shortly after an integration command or match the requested position are ignored as own movements.
- Test mode calculates positions but never calls `cover.set_cover_position`.
- The decision reason sensor exposes a `decision_details` attribute containing the live values and thresholds used for the decision (angle diff, elevation, temperature, checks, etc.). This keeps the sensor state compact while allowing detailed diagnostics.
- Decision logic (sun angle, weather, temperature, thresholds) lives in `decision.py` (`DecisionEngine`); `cover.py` only orchestrates evaluation, pause handling and command dispatch.
- Shared entity boilerplate (device info, cover lookup, state listeners) lives in `entities.py` mixins; sensors and button inherit from them.
- Presence-based pause extension is optional per group. Presence alone never starts a pause; it only holds (sticky) and extends (nachlauf) an existing manual pause. The reset button always takes precedence.
- When `use_forecast_max_temp` is enabled, the integration switches to proactive mode: `sun_calc.py` calculates when the sun will be at the window today (using `astral`), and `cover.py` fetches the hourly weather forecast at that time. The decision engine uses the forecast temperature and condition at the sun-in-window time instead of the current sun position. Fallback to `temp_forecast_entity` (day's max) if the hourly forecast is unavailable.
- Morning time is automatically shifted past the quiet window if it falls inside it (`trigger.py: _effective_morning_time`), so the morning evaluation is not swallowed by the quiet-time early return.

## Known Issues / TODOs
1. **HACS download URL mismatch**
   HACS was observed trying to download an archive using a commit hash instead of the branch name (`refs/heads/<commit>.zip`). This usually resolves after pushing a proper release or re-add the repository. Manual installation is the fallback.

2. **No automated tests yet**
   The project has no test suite. Add `tests/` with `pytest-homeassistant-custom-component` when expanding logic.

3. **Translation cache**
   If translation changes (including `data_description`) do not appear, restart Home Assistant to clear the translation cache.

## Development Workflow
1. Edit files in `custom_components/simple_smart_cover/`.
2. Validate Python syntax:
   ```bash
   python3 -m py_compile custom_components/simple_smart_cover/*.py
   ```
3. Validate translation JSON:
   ```bash
   python3 -m json.tool custom_components/simple_smart_cover/translations/de.json > /dev/null
   python3 -m json.tool custom_components/simple_smart_cover/translations/en.json > /dev/null
   ```
4. Push to GitHub.
5. In Home Assistant: reload the integration or restart HA.
6. If HACS is used, re-add or refresh the custom repository.

## Manual Installation (fallback)
Copy `custom_components/simple_smart_cover/` into the HA `config/custom_components/` directory and restart HA.

## Code Style
- Type hints encouraged (`from __future__ import annotations`).
- Constants live in `const.py`; do not hard-code config keys in logic files.
- Schema construction lives in `schemas.py` (`build_schema` / `build_duplicate_schema`); the config flow imports from there.
- Decision logic lives in `decision.py`; `cover.py` delegates to `DecisionEngine`.

## Migration Notes
`__init__.py` migrates old config keys to new names on setup using `MIGRATION_MAP` from `const.py`:
```python
MIGRATION_MAP = {
    "sunny_in_angle": "position_sunny_in_angle",
    "sunny_outside_angle": "position_sunny_outside_angle",
    "cloudy": "position_cloudy",
    "evening": "position_evening",
}
```
When renaming keys, extend this map and bump `manifest.json` version if breaking.
