# Simple Smart Cover

A Home Assistant integration for automating covers (rollershutters/blinds) based on weather forecast and sun position.

## Features

- **Automatic morning opening** at a configurable time
- **Weather-aware positioning** during the day with periodic re-evaluation
- **Sun shading** based on azimuth, elevation and temperature
- **Automatic closing** at sunset
- **Quiet mode** with a configurable time window
- **Pause after manual operation** so the interval check does not immediately override user input
- **Test mode** to observe behaviour without moving the covers
- One **cover entity** plus **sensors** for target position and decision reason per cover group

## Installation

### Option 1: Via HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. Open HACS and go to **Integrations**.
3. Click the three dots in the top right and select **Custom repositories**.
4. Paste your GitHub repository URL, e.g.:
   ```
   https://github.com/langfeld/home-assistant-simple-smart-cover
   ```
5. Select **Integration** as the category and confirm.
6. Search for **Simple Smart Cover** in HACS and install it.
7. Restart Home Assistant.
8. Go to **Settings → Devices & Services → Add Integration**.
9. Search for **Simple Smart Cover** and follow the setup dialog.

### Option 2: Manual

1. Download the files from the repository.
2. Copy the `custom_components/simple_smart_cover` folder into your Home Assistant `custom_components` directory:
   ```
   config/custom_components/simple_smart_cover/
   ```
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration**.
5. Search for **Simple Smart Cover** and follow the setup dialog.

## Entities per group

For each configured cover group the following entities are created:

- **`cover.<name>`** – Virtual cover with the computed target position
- **`sensor.<name>_target_position`** – Shows the computed target position in %
- **`sensor.<name>_decision`** – Shows the reason for the decision
- **`binary_sensor.<name>_pause_active`** – Shows whether the manual-operation pause is active
- **`sensor.<name>_pause_remaining`** – Shows the remaining pause time in minutes
- **`button.<name>_reset_pause`** – Resets the manual pause immediately

Possible values for the decision sensor:

- `cloudy` – cloudy weather
- `sunny_in_angle` – sun in the window angle and warm enough
- `sunny_outside_angle` – sun outside the angle or too cold
- `evening` – evening closing
- `quiet_time` – quiet mode active
- `manual_activity_pause` – pause after manual operation
- `weather_unavailable` – weather entity not available

### Diagnostic attributes

The decision sensor additionally exposes a `decision_details` attribute containing all current measurements and thresholds that led to the decision:

```yaml
decision_details:
  is_evening: false
  is_cloudy: false
  weather_condition: sunny
  sun_azimuth: 210.5
  sun_elevation: 45.2
  window_orientation: 180
  angle_diff: 30.5
  temperature: 22.3
  thresholds:
    sun_angle_tolerance: 25
    min_sun_elevation: 10
    temp_threshold: 20
  checks:
    angle_in_range: false
    elevation_high_enough: true
    temp_high_enough: true
```

This is especially helpful when the state is `sunny_outside_angle`: the `checks` object shows immediately whether the sun is outside the angle, too low, or it is too cold.

## Language

The integration ships with English and German translations. Home Assistant selects the language automatically based on your HA user interface language. Entity names are in English so they stay stable across language settings.

A German version of this README is available at [README.de.md](README.de.md).

## Note

This is a first version. Feedback and suggestions for improvement are welcome.
