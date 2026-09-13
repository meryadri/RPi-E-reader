"""
Google Calendar integration — today's all-day events, read-only.

Setup is a one-time job documented in README.md in this directory.

Usage from an app:

    from integrations import google_calendar as gcal

    gcal.start()                       # once, from App.setup
    snap = gcal.get_snapshot()         # never blocks, never raises
    snap.events                        # tuple of normalised event dicts
    snap.status                        # loading | ok | auth_required | error
"""
from .service import (  # noqa: F401
    AUTH_REQUIRED,
    ERROR,
    LOADING,
    OK,
    Snapshot,
    get_snapshot,
    is_running,
    start,
    stop,
    today,
)

__all__ = [
    "AUTH_REQUIRED", "ERROR", "LOADING", "OK",
    "Snapshot", "get_snapshot", "is_running", "start", "stop", "today",
]
