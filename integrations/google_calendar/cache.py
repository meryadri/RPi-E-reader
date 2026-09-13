"""
Last-good calendar snapshot on disk.

Purpose is narrow: make the very first frame after a reboot show real events
instead of "Checking calendar...", and keep showing something if the Wi-Fi is
down.  Follows apps/ereader/metrics_cache.py, with one deliberate difference —
see save().
"""
from __future__ import annotations

import json
import os
from datetime import date

from . import config


def load(today: date) -> list[dict] | None:
    """Cached events, but only if they are for `today`.

    Yesterday's all-day events rendered as today's is worse than showing
    nothing, so a stale-day cache is discarded rather than displayed.
    """
    try:
        if not config.CACHE_FILE.exists():
            return None
        with open(config.CACHE_FILE, "r") as f:
            blob = json.load(f)
        if blob.get("day") != today.isoformat():
            return None
        items = blob.get("events")
        if not isinstance(items, list):
            return None
        return items
    except Exception:
        return None


def save(day: date, items: list[dict]) -> None:
    try:
        config.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = config.CACHE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump({"day": day.isoformat(), "events": items}, f)
        # Atomic replace.  The refresh thread is a daemon and can be killed
        # mid-write at process exit; a plain open(..., "w") would leave a
        # truncated file behind.  (metrics_cache.py has this hazard — not worth
        # copying that part of the template.)
        os.replace(tmp, config.CACHE_FILE)
    except Exception:
        pass


def clear() -> None:
    try:
        config.CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass
