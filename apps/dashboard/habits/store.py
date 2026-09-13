"""
Reading and writing the private habit files.

Every function degrades rather than raising: these are reached from the render
path, and display/runtime.py:run() has no try/except above it.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import date

from . import config


def load_habits() -> list[str]:
    """The configured habit list in display order, or [] if not set up yet."""
    try:
        with open(config.HABITS_FILE) as f:
            raw = json.load(f)
        return [h.strip() for h in raw if isinstance(h, str) and h.strip()]
    except Exception:
        return []


def load_log() -> dict[str, list[str]]:
    """{"YYYY-MM-DD": [habit names completed that day]}."""
    try:
        with open(config.LOG_FILE) as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        return {
            day: [h for h in names if isinstance(h, str)]
            for day, names in raw.items()
            if isinstance(day, str) and isinstance(names, list)
        }
    except Exception:
        return {}


def save_log(log: dict[str, list[str]]) -> None:
    try:
        config.PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = config.LOG_FILE.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(log, f, indent=1, sort_keys=True)
        # Atomic: this is written from the Flask thread while a daemon thread may
        # be killed at process exit; a plain write could truncate the only copy
        # of the history.
        os.replace(tmp, config.LOG_FILE)
    except Exception:
        pass


def done_on(log: dict[str, list[str]], day: date) -> set[str]:
    return set(log.get(day.isoformat(), []))


def set_done(log: dict[str, list[str]], day: date, habit: str, done: bool) -> None:
    """Mutate `log` in place so `habit` is (or is not) recorded for `day`."""
    key = day.isoformat()
    names = set(log.get(key, []))
    if done:
        names.add(habit)
    else:
        names.discard(habit)
    if names:
        log[key] = sorted(names)
    else:
        # Don't leave empty lists around; an absent key means "nothing done".
        log.pop(key, None)


def load_token() -> str:
    """The URL token, generated on first use.

    Not authentication — it keeps the habit names off a casual scan of the home
    network, which is the actual risk. See private/README.md.
    """
    try:
        token = config.TOKEN_FILE.read_text().strip()
        if token:
            return token
    except Exception:
        pass

    token = secrets.token_urlsafe(16)
    try:
        config.PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        fd = os.open(config.TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token)
    except Exception:
        pass
    return token
