"""
Background refresh thread and the snapshot the dashboard reads.

Contract with the render path: get_snapshot() never blocks and never raises.
`display/runtime.py:run()` has no try/except anywhere, so anything escaping
render() kills the process and leaves a dead panel until someone SSHes in.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import cache, client, config
from .auth import AuthError, load_credentials

# Status values the dashboard distinguishes.
LOADING = "loading"
OK = "ok"
AUTH_REQUIRED = "auth_required"
ERROR = "error"


@dataclass(frozen=True)
class Snapshot:
    """An immutable view of calendar state.

    Frozen and replaced wholesale rather than mutated, so the render thread can
    never observe a half-updated list.  That removes the race by construction
    instead of by careful locking.
    """
    status: str = LOADING
    events: tuple[dict, ...] = ()
    day: date | None = None
    fetched_at: float | None = None
    partial: bool = False
    error: str | None = None
    version: int = 0

    def is_stale(self, now: float | None = None) -> bool:
        """Derived on read, not stored.

        A worker thread that died or hung cannot update its own status, so
        asking "how old is this data" on the main thread is the only check that
        catches a hung HTTP call as well as an outage.
        """
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
_service = None
_calendars: list[dict] = []
_last_day: date | None = None
_last_attempt: float = 0.0
_error_streak: int = 0
_started_at: float = 0.0


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def get_snapshot() -> Snapshot:
    """The current snapshot. Lock, read a reference, return — nothing else."""
    with _lock:
        return _snapshot


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def today() -> date:
    """Today in the configured zone.

    Callers comparing a Snapshot.day against "now" must use this, not
    date.today() — the Pi's system zone can differ from GCAL_TZ, and comparing
    across the two would silently hide every event.
    """
    return _today()


def start() -> None:
    """Start the refresh thread. Idempotent, fast, never does network I/O."""
    global _thread, _started_at
    if is_running():
        return

    _started_at = time.time()
    _stop.clear()

    # A small local JSON read, so the first frame after a reboot shows real
    # events rather than "Checking calendar...".
    today = _today()
    cached = cache.load(today)
    if cached:
        _publish(Snapshot(status=OK, events=tuple(cached), day=today, fetched_at=None))

    _thread = threading.Thread(target=_loop, name="gcal-refresh", daemon=True)
    _thread.start()


def stop() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2.0)
        _thread = None


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _today() -> date:
    return datetime.now(ZoneInfo(config.TIMEZONE)).date()


def _publish(new: Snapshot) -> None:
    """Publish only if the *rendered payload* changed, bumping version if so.

    This is the whole "only refresh the screen when the info changes" guarantee.
    A 30-minute poll that returns an identical event list must not bump the
    version, or the e-ink panel would refresh every 30 minutes for nothing.
    fetched_at moving on its own is explicitly not a change.
    """
    global _snapshot
    with _lock:
        old = _snapshot
        same = (
            old.status == new.status
            and old.events == new.events
            and old.day == new.day
            and old.partial == new.partial
            and old.error == new.error
        )
        if same:
            # Keep the fresher timestamp so staleness stays accurate, but leave
            # version alone so nothing redraws.
            _snapshot = replace(old, fetched_at=new.fetched_at)
        else:
            _snapshot = replace(new, version=old.version + 1)


def _backoff() -> float:
    idx = min(_error_streak, len(config.ERROR_BACKOFF_SECONDS)) - 1
    if idx < 0:
        return float(config.REFRESH_SECONDS)
    return float(min(config.ERROR_BACKOFF_SECONDS[idx], config.REFRESH_SECONDS))


def _refresh_once(today: date) -> None:
    """One full fetch cycle. Publishes a new snapshot; never raises."""
    global _service, _calendars, _last_day, _error_streak

    current = get_snapshot()

    try:
        creds = load_credentials()
    except AuthError as exc:
        # Distinguishing this from a network blip is the difference between a
        # dashboard that tells you how to fix it and one that just sits there.
        _error_streak += 1
        _publish(replace(
            current, status=AUTH_REQUIRED, error=str(exc), day=today, partial=False,
        ))
        return

    try:
        if _service is None:
            _service = client.build_service(creds)
        if not _calendars or _last_day != today:
            _calendars = client.list_calendars(_service)

        items, failed = client.fetch_all_day_events(_service, _calendars, today)
    except Exception as exc:
        _service = None  # rebuild next time; the creds may have rotated
        _error_streak += 1
        # Keep the last-good events rather than blanking the panel.
        if current.status == OK and current.day == today:
            _publish(replace(current, error=str(exc)))
        else:
            # Within the first couple of minutes this is probably just the Pi's
            # clock and network not being up yet (no RTC on a Pi Zero/3), so
            # stay on "loading" rather than showing an error.
            booting = (time.time() - _started_at) < 120
            _publish(replace(
                current,
                status=LOADING if booting else ERROR,
                error=str(exc),
                day=today,
            ))
        return

    if failed and len(failed) == len(_calendars):
        _error_streak += 1
        _publish(replace(current, error="all calendars failed"))
        return

    # Losing the primary calendar is worse than showing slightly stale data.
    primary_failed = any(c.get("primary") for c in failed)
    if primary_failed:
        _error_streak += 1
        _publish(replace(current, error="primary calendar unavailable"))
        return

    _error_streak = 0
    _last_day = today
    cache.save(today, items)
    _publish(Snapshot(
        status=OK,
        events=tuple(items),
        day=today,
        fetched_at=time.time(),
        partial=bool(failed),
        error=None,
    ))


def _loop() -> None:
    global _last_attempt
    while not _stop.is_set():
        try:
            today = _today()
            if _last_attempt == 0.0:
                due = True                              # first run
            elif _last_day != today and _error_streak == 0:
                due = True                              # midnight rollover
            else:
                # Covers both the ordinary interval and the error backoff.
                # Note _last_day only advances on success, so a failing fetch
                # keeps looking like a rollover — the _error_streak check above
                # is what stops it from retrying every single tick.
                due = (time.monotonic() - _last_attempt) >= _interval()
            if due:
                _last_attempt = time.monotonic()
                _refresh_once(today)
        except Exception:
            # The loop must never die; a dead worker means a frozen dashboard.
            pass
        _stop.wait(config.TICK_SECONDS)


def _interval() -> float:
    snap = get_snapshot()
    if snap.status == AUTH_REQUIRED:
        # A revoked token will not fix itself. Retrying every 30s just gets
        # you rate-limited.
        return float(config.AUTH_ERROR_BACKOFF_SECONDS)
    if _error_streak:
        return _backoff()
    return float(config.REFRESH_SECONDS)
