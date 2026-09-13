"""
Dashboard data provider.

Calendar (Google Calendar) and weather (Open-Meteo) are live.  Training is still
a hardcoded stub — this module remains the single seam to replace it with a real
source; the screen only ever calls these functions, so the UI does not change
when the data becomes live.
"""
from __future__ import annotations
from datetime import datetime

from integrations import google_calendar as gcal
from integrations import open_meteo


def get_now() -> datetime:
    """Current local time.  Real clock — safe to use as-is."""
    return datetime.now()


def get_weather_snapshot() -> open_meteo.Snapshot:
    """Current conditions plus their freshness/error state.

    Never blocks and never raises — called from render(), and
    display/runtime.py:run() has no try/except above it.
    """
    try:
        return open_meteo.get_snapshot()
    except Exception:
        return open_meteo.Snapshot(status=open_meteo.ERROR, error="weather unavailable")


def get_weather() -> dict:
    """Current conditions, as the screen renders them."""
    return get_weather_snapshot().weather


def start_sources() -> None:
    """Start background data refresh.  Wired to App.setup; must not block."""
    gcal.start()
    open_meteo.start()


def get_calendar() -> gcal.Snapshot:
    """Today's all-day events plus their freshness/error state.

    Never blocks and never raises — it is called from render(), and
    display/runtime.py:run() has no try/except above it.
    """
    try:
        return gcal.get_snapshot()
    except Exception:
        return gcal.Snapshot(status=gcal.ERROR, error="calendar unavailable")


def get_events() -> tuple[dict, ...]:
    """Today's all-day calendar events, in display order."""
    return get_calendar().events


def get_training() -> dict:
    """Today's running workout + plan context.  Replace with training-plan source."""
    return {
        "today": "Tempo run",
        "detail": "8 km @ 4:45/km",
        "week": "Wk 3 / 12",
        "volume": "32 km this week",
    }
