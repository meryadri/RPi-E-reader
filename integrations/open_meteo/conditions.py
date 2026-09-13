"""
WMO weather code interpretation — pure, no network, no JSON.

Open-Meteo reports conditions as a WMO 4677 code.  Turning that into an icon and
a short label is the only real logic in this integration, so it lives here where
pytest can reach it offline.
"""
from __future__ import annotations

# The icons the panel knows how to draw.  This set is derived from what WMO
# codes actually distinguish — fog and thunderstorm get their own icons because
# the API genuinely reports them, and nothing finer is worth drawing at 36px on
# a 1-bit panel.
CLEAR = "clear"
CLEAR_NIGHT = "clear_night"
PARTLY = "partly"
PARTLY_NIGHT = "partly_night"
CLOUDY = "cloudy"
FOG = "fog"
RAIN = "rain"
SNOW = "snow"
THUNDER = "thunder"

ICONS = frozenset({CLEAR, CLEAR_NIGHT, PARTLY, PARTLY_NIGHT,
                   CLOUDY, FOG, RAIN, SNOW, THUNDER})

UNKNOWN_DESCRIPTION = "--"

# Descriptions are kept short on purpose.  The condition line is right-aligned on
# the same row as the date, and a full WMO phrase like "Thunderstorm with slight
# hail" would run straight into it.  16 characters is the budget.
MAX_DESCRIPTION = 16

# code -> (icon, description)
_WMO: dict[int, tuple[str, str]] = {
    0:  (CLEAR,   "Clear"),
    1:  (PARTLY,  "Mainly clear"),
    2:  (PARTLY,  "Partly cloudy"),
    3:  (CLOUDY,  "Overcast"),
    45: (FOG,     "Fog"),
    48: (FOG,     "Freezing fog"),
    51: (RAIN,    "Light drizzle"),
    53: (RAIN,    "Drizzle"),
    55: (RAIN,    "Heavy drizzle"),
    56: (RAIN,    "Icy drizzle"),
    57: (RAIN,    "Icy drizzle"),
    61: (RAIN,    "Light rain"),
    63: (RAIN,    "Rain"),
    65: (RAIN,    "Heavy rain"),
    66: (RAIN,    "Freezing rain"),
    67: (RAIN,    "Freezing rain"),
    71: (SNOW,    "Light snow"),
    73: (SNOW,    "Snow"),
    75: (SNOW,    "Heavy snow"),
    77: (SNOW,    "Snow grains"),
    80: (RAIN,    "Light showers"),
    81: (RAIN,    "Showers"),
    82: (RAIN,    "Heavy showers"),
    85: (SNOW,    "Snow showers"),
    86: (SNOW,    "Snow showers"),
    95: (THUNDER, "Thunderstorm"),
    96: (THUNDER, "Thunderstorm"),
    99: (THUNDER, "Hailstorm"),
}


def describe(code, is_day: bool = True) -> tuple[str, str]:
    """Map a WMO code to (icon, description).

    Unknown or missing codes degrade to an overcast icon and "--" rather than
    raising — this runs on the render path's data, and the loop above render()
    has no exception handling.
    """
    try:
        icon, text = _WMO[int(code)]
    except (KeyError, TypeError, ValueError):
        return CLOUDY, UNKNOWN_DESCRIPTION
    if not is_day:
        # A sun at 11pm looks broken.
        icon = {CLEAR: CLEAR_NIGHT, PARTLY: PARTLY_NIGHT}.get(icon, icon)
    return icon, text


def c_to_f(celsius: float) -> int:
    """Celsius to whole Fahrenheit degrees.

    round() rather than int(), which truncates toward zero and would be wrong by
    a degree for the negative temperatures Boston gets all winter.
    """
    return round(celsius * 9 / 5 + 32)
