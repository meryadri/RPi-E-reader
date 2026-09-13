"""
In-memory habit state and the snapshot the dashboard renders.

The Flask server runs in this same process, so toggling from a phone mutates
this state directly and bumps `version` — the panel repaints on the next poll
tick without any file watching or IPC.

Contract with the render path: get_snapshot() never blocks and never raises.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, replace

from datetime import date

from . import config, stats, store


@dataclass(frozen=True)
class Snapshot:
    """An immutable view of today's checklist."""
    habits: tuple[str, ...] = ()
    done: frozenset[str] = frozenset()
    streaks: dict[str, int] = field(default_factory=dict)
    day: date | None = None
    version: int = 0

    @property
    def configured(self) -> bool:
        return bool(self.habits)

    def progress(self) -> tuple[int, int]:
        return sum(1 for h in self.habits if h in self.done), len(self.habits)


_lock = threading.Lock()
_snapshot = Snapshot()
_log: dict[str, list[str]] = {}
_thread: threading.Thread | None = None
_stop = threading.Event()


def get_snapshot() -> Snapshot:
    """The current snapshot. Lock, read a reference, return — nothing else."""
    with _lock:
        return _snapshot


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def start() -> None:
    """Load state and start the rollover watcher. Idempotent, never blocks."""
    global _thread
    reload_from_disk()
    if is_running():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="habit-rollover", daemon=True)
    _thread.start()


def stop() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2.0)
        _thread = None


def reload_from_disk() -> None:
    """Re-read habits and log from private/ and republish."""
    global _log
    habits = store.load_habits()
    _log = store.load_log()
    _publish_for(habits, config.habit_day())


def toggle(habit: str) -> bool:
    """Flip one habit for the current habit-day.  Returns its new state."""
    snap = get_snapshot()
    if habit not in snap.habits:
        return False

    day = config.habit_day()
    now_done = habit not in snap.done

    with _lock:
        store.set_done(_log, day, habit, now_done)
        log_copy = {k: list(v) for k, v in _log.items()}

    # Written outside the lock so a slow disk cannot stall the render thread.
    store.save_log(log_copy)
    _publish_for(list(snap.habits), day)
    return now_done


def get_log() -> dict[str, list[str]]:
    """A copy of the full history, for the history page."""
    with _lock:
        return {k: list(v) for k, v in _log.items()}


def _publish_for(habits: list[str], day: date) -> None:
    """Rebuild the snapshot, bumping version only if the panel would differ."""
    global _snapshot
    with _lock:
        done = frozenset(store.done_on(_log, day))
        new_streaks = stats.streaks(_log, habits, day)
        old = _snapshot
        same = (
            tuple(habits) == old.habits
            and done == old.done
            and new_streaks == old.streaks
            and day == old.day
        )
        if same:
            return
        _snapshot = replace(
            old,
            habits=tuple(habits),
            done=done,
            streaks=new_streaks,
            day=day,
            version=old.version + 1,
        )


def _loop() -> None:
    """Watch for the habit-day rolling over at ROLLOVER_HOUR."""
    while not _stop.is_set():
        try:
            day = config.habit_day()
            if day != get_snapshot().day:
                _publish_for(list(get_snapshot().habits), day)
        except Exception:
            # The loop must never die; a dead worker means a frozen checklist.
            pass
        _stop.wait(config.TICK_SECONDS)
