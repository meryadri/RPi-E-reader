"""
Open-Meteo weather integration — current conditions, no API key required.

Usage from an app:

    from integrations import open_meteo

    open_meteo.start()                  # once, from App.setup
    snap = open_meteo.get_snapshot()    # never blocks, never raises
    snap.weather["temp_c"]
"""
from .service import (  # noqa: F401
    ERROR,
    LOADING,
    OK,
    Snapshot,
    get_snapshot,
    is_running,
    start,
    stop,
)

__all__ = [
    "ERROR", "LOADING", "OK",
    "Snapshot", "get_snapshot", "is_running", "start", "stop",
]
