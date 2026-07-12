"""
Dashboard data provider — PROOF-OF-CONCEPT STUB.

Every function returns hardcoded data for now.  This module is the single seam
to replace later with real sources (weather API, Google Calendar, a training-plan
upload site, etc.); the screen code only ever calls these functions, so the UI
does not change when the data becomes live.
"""
from __future__ import annotations
from datetime import datetime


def get_now() -> datetime:
    """Current local time.  Real clock — safe to use as-is."""
    return datetime.now()


def get_weather() -> dict:
    """Current conditions.  Replace with a weather API call."""
    return {"temp_c": 24, "condition": "Clear", "icon": "☀"}


def get_events() -> list[dict]:
    """Today's calendar events, earliest first.  Replace with Google Calendar."""
    return [
        {"time": "09:00", "title": "Standup"},
        {"time": "13:00", "title": "Lunch w/ Alex"},
        {"time": "18:30", "title": "Gym"},
    ]


def get_training() -> dict:
    """Today's running workout + plan context.  Replace with training-plan source."""
    return {
        "today": "Tempo run",
        "detail": "8 km @ 4:45/km",
        "week": "Wk 3 / 12",
        "volume": "32 km this week",
    }
