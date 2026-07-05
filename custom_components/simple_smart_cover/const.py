"""Constants for the Simple Smart Cover integration."""

DOMAIN = "simple_smart_cover"

CONF_COVERS = "covers"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_MORNING_TIME = "morning_time"
CONF_ENABLE_MORNING = "enable_morning"
CONF_ENABLE_EVENING = "enable_evening"
CONF_WINDOW_ORIENTATION = "window_orientation"
CONF_SUN_ANGLE_TOLERANCE = "sun_angle_tolerance"
CONF_MIN_SUN_ELEVATION = "min_sun_elevation"
CONF_TEMP_THRESHOLD = "temp_threshold"
CONF_TEMP_SOURCE = "temp_source"
CONF_USE_FORECAST_MAX_TEMP = "use_forecast_max_temp"
CONF_TEMP_FORECAST_ENTITY = "temp_forecast_entity"
CONF_CLOUDY_CONDITIONS = "cloudy_conditions"
CONF_POSITIONS = "positions"
CONF_POSITION_SUNNY_IN_ANGLE = "sunny_in_angle"
CONF_POSITION_SUNNY_OUTSIDE_ANGLE = "sunny_outside_angle"
CONF_POSITION_CLOUDY = "cloudy"
CONF_POSITION_EVENING = "evening"
CONF_INVERT_POSITIONS = "invert_positions"
CONF_ENABLE_QUIET_MODE = "enable_quiet_mode"
CONF_QUIET_START = "quiet_start"
CONF_QUIET_END = "quiet_end"
CONF_ENABLE_REEVALUATION = "enable_reevaluation"
CONF_REEVALUATE_INTERVAL = "reevaluate_interval"
CONF_MIN_POSITION_CHANGE = "min_position_change"
CONF_ENABLE_MANUAL_ACTIVITY_PAUSE = "enable_manual_activity_pause"
CONF_MANUAL_ACTIVITY_DURATION = "manual_activity_duration"
CONF_TEST_MODE = "test_mode"

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
