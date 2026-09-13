"""
Dashboard data provider.

All three columns are live: calendar (Google Calendar), weather (Open-Meteo)
and the daily habit checklist (local, see private/README.md).  The screen only
ever calls these functions, so the seam stays in one place.
"""
from __future__ import annotations
from datetime import datetime

from integrations import google_calendar as gcal
from integrations import open_meteo
from apps.dashboard import habits


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
    habits.start()
    habits.start_server()
    print(f"Habits: {habits.url()}")


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


def get_habits() -> habits.Snapshot:
    """Today's habit checklist.

    Never blocks and never raises — called from render(), and
    display/runtime.py:run() has no try/except above it.
    """
    try:
        return habits.get_snapshot()
    except Exception:
        return habits.Snapshot()
