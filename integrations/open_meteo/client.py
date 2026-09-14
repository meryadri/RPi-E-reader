"""
The single Open-Meteo request.

Stdlib urllib rather than requests — one GET with a timeout does not justify a
new dependency on a Raspberry Pi.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from . import conditions, config

_FIELDS = (
    "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day"
)


def build_url(lat: float, lon: float) -> str:
    query = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": _FIELDS,
        "wind_speed_unit": config.WIND_SPEED_UNIT,
        "timezone": "auto",
    })
    return f"{config.BASE_URL}?{query}"


def parse(payload: dict) -> dict:
    """Normalise a response into the dict the dashboard renders.

    Every key is always present: render() indexes these unguarded and has no
    try/except above it, so a None would take down the process.
    """
    current = payload.get("current") or {}

    temp_c = current.get("temperature_2m")
    if temp_c is None:
        raise ValueError("response has no temperature")

    feels_c = current.get("apparent_temperature")
    if feels_c is None:
        feels_c = temp_c

    is_day = bool(current.get("is_day", 1))
    icon, description = conditions.describe(current.get("weather_code"), is_day)

    wind = current.get("wind_speed_10m") or 0

    return {
        "temp_c": round(temp_c),
        "temp_f": conditions.c_to_f(temp_c),
        "feels_c": round(feels_c),
        "feels_f": conditions.c_to_f(feels_c),
        "icon": icon,
        "description": description,
        "wind": round(wind),
        "wind_unit": config.WIND_LABEL,
        "is_day": is_day,
    }


def fetch(lat: float | None = None, lon: float | None = None) -> dict:
    """Fetch current conditions.  Raises on network or parse failure."""
    url = build_url(
        config.LATITUDE if lat is None else lat,
        config.LONGITUDE if lon is None else lon,
    )
    req = urllib.request.Request(url, headers={"User-Agent": "rpi-eink-dashboard"})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return parse(payload)
