"""Sun position calculations for Simple Smart Cover.

Uses the ``astral`` library (a Home Assistant dependency) to calculate the
sun's azimuth and elevation at future times. This allows the integration to
determine when the sun will be at the window today, enabling proactive cover
positioning based on forecast data instead of the current sun position only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Sampling interval for the sun position scan. The sun moves ~0.25°/min, so
# with a 10-minute interval and a typical tolerance of 45° we never miss the
# window.
_SAMPLE_INTERVAL = timedelta(minutes=10)


def get_sun_in_window_time(
    hass: HomeAssistant,
    window_orientation: float,
    tolerance: float,
    min_elevation: float,
) -> datetime | None:
    """Return the first time today when the sun enters the window.

    Samples the sun's azimuth at regular intervals from now until sunset.
    Returns the first datetime at which the azimuth is within *tolerance* of
    *window_orientation* AND the elevation is at least *min_elevation*.

    Returns ``None`` if the sun does not reach the window today.

    Raises ``RuntimeError`` if the calculation itself fails (e.g. ``astral``
    not importable, location misconfigured) so the caller can fall back to
    the reactive (current-position) decision path.
    """
    try:
        from astral import LocationInfo
        from astral.sun import azimuth, elevation, sun as astral_sun
    except ImportError as exc:
        raise RuntimeError("astral library not available") from exc

    lat = hass.config.latitude
    lon = hass.config.longitude
    tz_name = str(hass.config.time_zone)

    try:
        loc = LocationInfo("HA", "HA", tz_name, lat, lon)
    except Exception as exc:
        raise RuntimeError(f"Could not create astral LocationInfo: {exc}") from exc

    now = dt_util.now()

    try:
        s = astral_sun(loc, date=now.date())
        sunrise = s["sunrise"]
        sunset = s["sunset"]
    except Exception as exc:
        raise RuntimeError(f"Could not calculate sunrise/sunset: {exc}") from exc

    if now > sunset:
        return None

    start = max(now, sunrise)
    end = sunset

    current = start
    while current <= end:
        az = _safe_call(azimuth, loc, current)
        el = _safe_call(elevation, loc, current)
        if az is None or el is None:
            break

        angle_diff = abs((az - window_orientation + 180) % 360 - 180)
        if angle_diff <= tolerance and el >= min_elevation:
            return current

        current += _SAMPLE_INTERVAL

    return None


def _safe_call(fn, loc, dt: datetime) -> float | None:
    """Call an astral sun function with API-compatibility handling.

    Different astral versions accept either ``loc.observer`` or ``loc``
    as the first argument. Try the modern API first, fall back gracefully.
    """
    try:
        return float(fn(loc.observer, dt))
    except (TypeError, AttributeError):
        try:
            return float(fn(loc, dt))
        except Exception:
            return None
