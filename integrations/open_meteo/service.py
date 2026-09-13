"""
Background weather refresh and the snapshot the dashboard reads.

Contract with the render path: get_snapshot() never blocks and never raises.
`display/runtime.py:run()` has no try/except anywhere, so anything escaping
render() kills the process and leaves a dead panel.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime

from . import cache, client, config

LOADING = "loading"
OK = "ok"
ERROR = "error"

# What the panel shows before the first successful fetch.
PLACEHOLDER: dict = {
    "temp_c": None, "temp_f": None, "feels_c": None, "feels_f": None,
    "icon": None, "description": "", "wind": None,
    "wind_unit": config.WIND_LABEL, "is_day": True,
}


@dataclass(frozen=True)
class Snapshot:
    """An immutable view of current conditions.

    Frozen and replaced wholesale rather than mutated, so the render thread can
    never see a half-updated reading.
    """
    status: str = LOADING
    weather: dict = None            # type: ignore[assignment]
    fetched_at: float | None = None
    error: str | None = None
    version: int = 0

    def __post_init__(self):
        if self.weather is None:
            object.__setattr__(self, "weather", dict(PLACEHOLDER))

    def is_stale(self, now: float | None = None) -> bool:
        """Derived on read, so a worker that died or hung is also caught."""
        if self.fetched_at is None:
            return self.status == OK
        now = time.time() if now is None else now
        return (now - self.fetched_at) > config.STALE_AFTER_SECONDS

    def fetched_at_label(self) -> str:
        if self.fetched_at is None:
            return ""
        return datetime.fromtimestamp(self.fetched_at).strftime("%H:%M")


_lock = threading.Lock()
_snapshot = Snapshot()
_thread: threading.Thread | None = None
_stop = threading.Event()
_last_attempt: float = 0.0
_error_streak: int = 0


def get_snapshot() -> Snapshot:
    """The current snapshot. Lock, read a reference, return — nothing else."""
    with _lock:
        return _snapshot


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def start() -> None:
    """Start the refresh thread. Idempotent, fast, never does network I/O."""
    global _thread
    if is_running():
        return
    _stop.clear()

    cached = cache.load()
    if cached:
        # fetched_at stays None so this reads as stale until a real fetch lands.
        _publish(Snapshot(status=OK, weather=cached))

    _thread = threading.Thread(target=_loop, name="weather-refresh", daemon=True)
    _thread.start()


def stop() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2.0)
        _thread = None


def _publish(new: Snapshot) -> None:
    """Publish, bumping version only if the *rendered* values changed.

    Temperatures and wind are already rounded to whole units by client.parse(),
    so a drift from 18.2 to 18.4 compares equal and writes nothing to the panel.
    A moving fetched_at on its own is explicitly not a change.
    """
    global _snapshot
    with _lock:
        old = _snapshot
        same = (
            old.status == new.status
            and old.weather == new.weather
            and old.error == new.error
        )
        if same:
            _snapshot = replace(old, fetched_at=new.fetched_at)
        else:
            _snapshot = replace(new, version=old.version + 1)


def _interval() -> float:
    if _error_streak:
        idx = min(_error_streak, len(config.ERROR_BACKOFF_SECONDS)) - 1
        return float(min(config.ERROR_BACKOFF_SECONDS[idx], config.REFRESH_SECONDS))
    return float(config.REFRESH_SECONDS)


def _refresh_once() -> None:
    """One fetch cycle. Publishes a snapshot; never raises."""
    global _error_streak

    current = get_snapshot()
    try:
        weather = client.fetch()
    except Exception as exc:
        _error_streak += 1
        if current.status == OK:
            # Keep the last-good reading on screen rather than blanking it.
            _publish(replace(current, error=str(exc)))
        else:
            _publish(replace(current, status=ERROR, error=str(exc)))
        return

    _error_streak = 0
    cache.save(weather)
    _publish(Snapshot(status=OK, weather=weather, fetched_at=time.time(), error=None))


def _loop() -> None:
    global _last_attempt
    while not _stop.is_set():
        try:
            if _last_attempt == 0.0 or (time.monotonic() - _last_attempt) >= _interval():
                _last_attempt = time.monotonic()
                _refresh_once()
        except Exception:
            # The loop must never die; a dead worker means a frozen reading.
            pass
        _stop.wait(config.TICK_SECONDS)
