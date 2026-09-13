"""
Last-good weather reading on disk.

Narrow purpose: show a real temperature on the first frame after a reboot,
instead of "--", and keep showing one if the Wi-Fi is down.
"""
from __future__ import annotations

import json
import os

from . import config


def load() -> dict | None:
    """The cached reading, or None.

    Unlike the calendar cache there is no day check — a temperature from an hour
    ago is still worth showing, and staleness is surfaced separately.
    """
    try:
        if not config.CACHE_FILE.exists():
            return None
        with open(config.CACHE_FILE) as f:
            blob = json.load(f)
        weather = blob.get("weather")
        if not isinstance(weather, dict) or "temp_c" not in weather:
            return None
        return weather
    except Exception:
        return None


def save(weather: dict) -> None:
    try:
        config.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = config.CACHE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump({"weather": weather}, f)
        # Atomic: the refresh thread is a daemon and can be killed mid-write at
        # process exit, which would otherwise leave a truncated file.
        os.replace(tmp, config.CACHE_FILE)
    except Exception:
        pass


def clear() -> None:
    try:
        config.CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass
