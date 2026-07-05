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

No manual Helpers are required; values are exposed as native integration sensors.

## Repository Layout
```
home-assistant-simple-smart-cover/
├── custom_components/simple_smart_cover/
│   ├── __init__.py          # Entry setup/unload, migration of old config keys
│   ├── manifest.json        # Integration manifest
│   ├── config_flow.py       # Config + Options flow
│   ├── const.py             # All config keys and defaults
│   ├── cover.py             # Virtual cover entity + decision logic
│   ├── sensor.py            # Target position & decision reason sensors
│   ├── trigger.py           # Time/sun-based re-evaluation triggers
│   ├── translations/de.json # German UI translations
│   ├── icon.png             # Brand icon for HA integration card (128x128)
│   ├── icon@2x.png          # Brand icon retina (256x256)
│   ├── logo.png             # Larger brand icon (256x256)
│   └── logo@2x.png          # Larger brand icon retina (512x512)
├── brands/simple_smart_cover/ # Ready-to-use files for home-assistant/brands PR
├── hacs.json                # HACS metadata
├── icon.svg                 # Source SVG for the brand icon
├── .gitignore
└── README.md
```

## Domain
`simple_smart_cover`

## Key Design Decisions
- Config flow driven by `voluptuous` schemas.
- Options flow allows editing the entry afterwards.
- Optional entity selectors (e.g. temperature sensors) must be nulled on clear; use `_optional_entities()` before saving.
- Cover entity reads `{**config_entry.data, **config_entry.options}` so option changes take effect immediately.
- Test mode calculates positions but never calls `cover.set_cover_position`.

## Known Issues / TODOs
1. **Pause sensor refresh is event-driven only**
   The pause sensors update when a bound cover changes state and when the cover entity updates. They do not have an independent timer, so the "remaining minutes" sensor may lag up to the next trigger interval after the pause expires.

2. **Fragile cover entity lookup in `__init__.py`**
   The trigger setup guesses the cover entity id as:
   ```python
   cover_entity_id = f"cover.{entry.data['name'].lower().replace(' ', '_')}"
   ```
   This is unreliable if HA slugifies differently or the entity registry assigns another id. Prefer looking up the entity via the entity registry by `unique_id` (`f"{entry.entry_id}_cover"`).

2. **HACS download URL mismatch**
   HACS was observed trying to download an archive using a commit hash instead of the branch name (`refs/heads/<commit>.zip`). This usually resolves after pushing a proper release or re-adding the repository. Manual installation is the fallback.

3. **No automated tests yet**
   The project has no test suite. Add `tests/` with `pytest-homeassistant-custom-component` when expanding logic.

4. **Translation cache**
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
   ```
4. Push to GitHub.
5. In Home Assistant: reload the integration or restart HA.
6. If HACS is used, re-add or refresh the custom repository.

## Manual Installation (fallback)
Copy `custom_components/simple_smart_cover/` into the HA `config/custom_components/` directory and restart HA.

## Code Style
- Type hints encouraged (`from __future__ import annotations`).
- Constants live in `const.py`; do not hard-code config keys in logic files.
- Keep config flow and options flow schema generation shared via `_get_schema(defaults)`.

## Migration Notes
`__init__.py` migrates old config keys to new names on setup:
```python
{
    "sunny_in_angle": "position_sunny_in_angle",
    "sunny_outside_angle": "position_sunny_outside_angle",
    "cloudy": "position_cloudy",
    "evening": "position_evening",
}
```
When renaming keys, extend this map and bump `manifest.json` version if breaking.
