"""
Tunables for the Open-Meteo weather integration.

No credentials — Open-Meteo needs no API key, so there is nothing secret here
and nothing to copy to the Pi.
"""
from __future__ import annotations
import os
from pathlib import Path

# Repo root: integrations/open_meteo/config.py → parents[1]
_ROOT = Path(__file__).resolve().parents[2]

CACHE_FILE = _ROOT / "data" / "weather_cache.json"

# --- Location ---------------------------------------------------------------

# Boston, MA.  Override with WEATHER_LAT / WEATHER_LON.
LATITUDE = float(os.environ.get("WEATHER_LAT", 42.325))
LONGITUDE = float(os.environ.get("WEATHER_LON", -71.085))

# --- Units ------------------------------------------------------------------

# Temperature is always requested in Celsius and converted to Fahrenheit
# locally, so one request serves both readings.
WIND_SPEED_UNIT = os.environ.get("WEATHER_WIND_UNIT", "kmh")   # kmh | mph | ms | kn
WIND_LABEL = {"kmh": "km/h", "mph": "mph", "ms": "m/s", "kn": "kn"}.get(
    WIND_SPEED_UNIT, WIND_SPEED_UNIT
)

# --- Refresh ----------------------------------------------------------------

# Open-Meteo refreshes its current-conditions data on roughly this cadence, so
# polling faster only burns power.  96 requests/day is far inside their
# fair-use guidance for non-commercial use.
REFRESH_SECONDS = int(os.environ.get("WEATHER_REFRESH_SECONDS", 15 * 60))

# How often the worker wakes to check whether a refresh is due.
TICK_SECONDS = 30

ERROR_BACKOFF_SECONDS = (30, 60, 120, 300)

# Age at which the reading is treated as stale.
STALE_AFTER_SECONDS = int(os.environ.get("WEATHER_STALE_AFTER", 60 * 60))

# --- Network ----------------------------------------------------------------

# Without a timeout, a half-open socket on flaky Wi-Fi hangs the worker thread
# forever.  Python cannot kill a thread, so this is the only thing standing
# between a dropped packet and a dashboard frozen until reboot.
HTTP_TIMEOUT_SECONDS = 10

BASE_URL = "https://api.open-meteo.com/v1/forecast"
