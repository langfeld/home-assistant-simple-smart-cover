# Simple Smart Cover

A Home Assistant integration for automating covers (rollershutters/blinds) based on weather forecast and sun position.

## Features

- **Automatic morning opening** at a configurable time
- **Weather-aware positioning** during the day with periodic re-evaluation
- **Sun shading** based on azimuth, elevation and temperature
- **Automatic closing** at sunset
- **Quiet mode** with a configurable time window (morning time is automatically shifted past the quiet window if it falls inside it)
- **Pause after manual operation** so the interval check does not immediately override user input
- **Presence-aware pause extension** to keep the automation from fighting the user while a room is occupied (optional, per group)
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
- **`binary_sensor.<name>_presence_lock`** – Shows whether the pause is currently held by presence (sticky or cooldown)
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

### Presence-aware pause extension

Optionally, a presence/motion binary sensor can be configured per cover group. Presence **alone never starts a pause** — it only extends an existing manual pause so the automation does not move the covers while a room is occupied.

Behaviour once a manual pause has been triggered (e.g. someone opened a cover by hand):

- While the configured presence sensor is `on`, the pause stays **sticky** and does not count down, regardless of the manual pause duration.
- After the presence sensor turns `off`, the pause keeps running for the configured **cooldown** (presence pause extension, in minutes). This prevents the automation from intervening during short absences (e.g. grabbing something from the kitchen).
- When the cooldown elapses (or no sensor is configured), the manual pause timer counts down as usual.
- The reset button always clears both the manual pause and the cooldown immediately, even while presence is still `on`.

Configuration fields:

- **`presence_sensor`** – Optional binary sensor (e.g. motion, occupancy or presence detector).
- **`presence_pause_extension`** – Cooldown in minutes after the sensor turns `off`. Set to `0` for sticky-only behaviour (no cooldown).

The `pause remaining` sensor reports the configured cooldown value while presence holds the pause sticky (the time the pause would still run if the user left now), and counts down from the off-transition during the cooldown.

### Morning time and quiet mode

If the configured morning time falls inside the quiet window, the morning trigger is automatically shifted to one second after the quiet window ends. Otherwise the morning evaluation would return `quiet_time` and no movement would happen, leaving the covers at the evening position for the rest of the day (especially when periodic re-evaluation is disabled). The shift is logged in the Home Assistant log so the effective trigger time is visible.

### Proactive forecast mode (use daily maximum temperature)

When **use daily maximum temperature** is enabled, the integration switches from reactive to proactive decision-making:

1. **Sun-in-window calculation**: at evaluation time (e.g. morning), the integration calculates at what time today the sun will enter the configured window (azimuth within tolerance, elevation above minimum). This uses the `astral` library (a Home Assistant dependency) with your HA location settings.
2. **Forecast lookup**: if the sun will reach the window today, the hourly weather forecast is fetched and the temperature and weather condition at the sun-in-window time are extracted.
3. **Decision**: the decision uses the forecast temperature and condition at that time — not the current sun position or current temperature. This means the covers can be positioned for the whole day at the morning evaluation, even if the sun does not reach the window until the afternoon.
4. **Fallback**: if the hourly forecast cannot be determined (e.g. the weather entity does not provide one), the integration falls back to the configured daily max temperature sensor and the current weather condition.

This mode is especially useful when periodic re-evaluation is disabled: the morning evaluation makes a single, informed decision for the entire day based on the forecast at the relevant sun-in-window time.

The `decision_details` attribute shows `forecast_mode: true` and `sun_in_window_time` (ISO timestamp) when this mode is active, so you can verify the calculated time and forecast values in the diagnostic sensor.

## Language

The integration ships with English and German translations. Home Assistant selects the language automatically based on your HA user interface language. Entity names are in English so they stay stable across language settings.

A German version of this README is available at [README.de.md](README.de.md).

## Lovelace Custom Card

A dedicated Lovelace card for this integration is available in a separate repository: [home-assistant-simple-smart-cover-card](https://github.com/langfeld/home-assistant-simple-smart-cover-card).

It displays the target position, the current decision reason, optional decision details, and provides three sliders to directly adjust the configured positions (sun in angle, sun outside, cloudy). The sliders call the `simple_smart_cover.set_positions` service on release.

Install via HACS (type: Dashboard) or manually — see the card repository for details.

## Note

This is a first version. Feedback and suggestions for improvement are welcome.
