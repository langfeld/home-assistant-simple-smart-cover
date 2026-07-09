"""Constants for the Simple Smart Cover integration.

All configuration keys, default values and reusable label maps live here so
that logic files never hard-code config keys or UI strings.
"""

# ---------------------------------------------------------------------------
# Integration domain
# ---------------------------------------------------------------------------

DOMAIN = "simple_smart_cover"

# ---------------------------------------------------------------------------
# Configuration keys
# ---------------------------------------------------------------------------

# Group definition
CONF_COVERS = "covers"
CONF_WEATHER_ENTITY = "weather_entity"

# Time based triggers
CONF_MORNING_TIME = "morning_time"
CONF_ENABLE_MORNING = "enable_morning"
CONF_ENABLE_EVENING = "enable_evening"

# Sun / window geometry
CONF_WINDOW_ORIENTATION = "window_orientation"
CONF_SUN_ANGLE_TOLERANCE = "sun_angle_tolerance"
CONF_MIN_SUN_ELEVATION = "min_sun_elevation"

# Temperature
CONF_TEMP_THRESHOLD = "temp_threshold"
CONF_TEMP_SOURCE = "temp_source"
CONF_USE_FORECAST_MAX_TEMP = "use_forecast_max_temp"
CONF_TEMP_FORECAST_ENTITY = "temp_forecast_entity"

# Weather conditions
CONF_CLOUDY_CONDITIONS = "cloudy_conditions"

# Positions
CONF_POSITIONS = "positions"
CONF_POSITION_SUNNY_IN_ANGLE = "position_sunny_in_angle"
CONF_POSITION_SUNNY_OUTSIDE_ANGLE = "position_sunny_outside_angle"
CONF_POSITION_CLOUDY = "position_cloudy"
CONF_POSITION_EVENING = "position_evening"
CONF_INVERT_POSITIONS = "invert_positions"

# Quiet mode
CONF_ENABLE_QUIET_MODE = "enable_quiet_mode"
CONF_QUIET_START = "quiet_start"
CONF_QUIET_END = "quiet_end"

# Reevaluation
CONF_ENABLE_REEVALUATION = "enable_reevaluation"
CONF_REEVALUATE_INTERVAL = "reevaluate_interval"
CONF_MIN_POSITION_CHANGE = "min_position_change"

# Manual activity pause
CONF_ENABLE_MANUAL_ACTIVITY_PAUSE = "enable_manual_activity_pause"
CONF_MANUAL_ACTIVITY_DURATION = "manual_activity_duration"

# Test mode
CONF_TEST_MODE = "test_mode"

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

DEFAULT_MORNING_TIME = "07:00:00"
DEFAULT_WINDOW_ORIENTATION = 180
DEFAULT_SUN_ANGLE_TOLERANCE = 45
DEFAULT_MIN_SUN_ELEVATION = 10
DEFAULT_TEMP_THRESHOLD = 22.0
DEFAULT_CLOUDY_CONDITIONS = [
    "cloudy",
    "partlycloudy",
    "fog",
    "rainy",
    "pouring",
    "snowy",
    "snowy-rainy",
    "hail",
    "lightning",
    "lightning-rainy",
    "windy",
    "windy-variant",
    "exceptional",
]
DEFAULT_POSITION_SUNNY_IN_ANGLE = 60
DEFAULT_POSITION_SUNNY_OUTSIDE_ANGLE = 100
DEFAULT_POSITION_CLOUDY = 100
DEFAULT_POSITION_EVENING = 0
DEFAULT_REEVALUATE_INTERVAL = "30"
DEFAULT_MIN_POSITION_CHANGE = 5
DEFAULT_MANUAL_ACTIVITY_DURATION = 15

# ---------------------------------------------------------------------------
# Config migration
# ---------------------------------------------------------------------------

# Old config keys mapped to their new names. Applied on setup so existing
# entries keep working after a rename.
MIGRATION_MAP = {
    "sunny_in_angle": CONF_POSITION_SUNNY_IN_ANGLE,
    "sunny_outside_angle": CONF_POSITION_SUNNY_OUTSIDE_ANGLE,
    "cloudy": CONF_POSITION_CLOUDY,
    "evening": CONF_POSITION_EVENING,
}

# ---------------------------------------------------------------------------
# UI labels (English base; UI strings in translations override these only when
# the HA frontend renders the config flow. Labels here are also used for the
# select dropdown option labels which voluptuous stores as data.)
# ---------------------------------------------------------------------------

# Weather condition options shown in the cloudy_conditions multi-select.
WEATHER_CONDITION_LABELS = [
    {"label": "Sunny", "value": "sunny"},
    {"label": "Clear (night)", "value": "clear-night"},
    {"label": "Partly cloudy", "value": "partlycloudy"},
    {"label": "Cloudy", "value": "cloudy"},
    {"label": "Fog", "value": "fog"},
    {"label": "Rainy", "value": "rainy"},
    {"label": "Pouring", "value": "pouring"},
    {"label": "Snowy", "value": "snowy"},
    {"label": "Snowy-rainy", "value": "snowy-rainy"},
    {"label": "Hail", "value": "hail"},
    {"label": "Lightning", "value": "lightning"},
    {"label": "Lightning with rain", "value": "lightning-rainy"},
    {"label": "Windy", "value": "windy"},
    {"label": "Windy, variant", "value": "windy-variant"},
    {"label": "Exceptional", "value": "exceptional"},
]

# Reevaluation interval dropdown options.
REEVALUATE_INTERVAL_LABELS = [
    {"label": "15 minutes", "value": "15"},
    {"label": "30 minutes", "value": "30"},
    {"label": "60 minutes", "value": "60"},
]

# Reevaluation interval value -> kwargs for async_track_time_change.
REEVALUATE_INTERVAL_TRACKING = {
    "15": {"minute": "/15"},
    "30": {"minute": "/30"},
    "60": {"minute": "0"},
}

# Suffix appended when generating a unique name for a duplicated entry.
COPY_SUFFIX = "Copy"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_valid_time(value: str) -> bool:
    """Validate a time string in HH:MM:SS format."""
    try:
        parts = value.split(":")
        if len(parts) != 3:
            return False
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59
    except (ValueError, AttributeError):
        return False
