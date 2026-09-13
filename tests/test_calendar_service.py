"""
Refresh-service and cache tests.

_refresh_once() is driven directly with a stubbed fetch — the thread is never
started and nothing ever sleeps.
"""
import json
from datetime import date

import pytest

from integrations.google_calendar import cache, config, service
from integrations.google_calendar.auth import AuthError

TODAY = date(2026, 9, 12)


def make_event(title, start="2026-09-12", end="2026-09-13"):
    return {
        "id": f"cal:{title}", "ical_uid": title, "title": title, "all_day": True,
        "start_date": start, "end_date": end, "days_total": 1, "day_index": 0,
        "calendar_id": "cal", "calendar_name": "Cal", "event_type": "default",
    }


@pytest.fixture(autouse=True)
def reset(tmp_path, monkeypatch):
    """Isolate module globals and the cache file between tests."""
    monkeypatch.setattr(config, "CACHE_FILE", tmp_path / "calendar_cache.json")
    service._snapshot = service.Snapshot()
    service._service = object()          # pretend the API client is built
    service._calendars = [{"id": "cal", "name": "Cal", "primary": True}]
    service._last_day = None
    service._error_streak = 0
    service._started_at = 0.0            # not "booting"
    monkeypatch.setattr(service, "load_credentials", lambda: object())
    monkeypatch.setattr(service.client, "build_service", lambda creds: object())
    # Return whatever the test set on service._calendars, so _refresh_once's
    # "re-list calendars on a new day" branch is a no-op here.
    monkeypatch.setattr(service.client, "list_calendars", lambda svc: service._calendars)
    yield


def stub_fetch(monkeypatch, items, failed=()):
    monkeypatch.setattr(
        service.client, "fetch_all_day_events",
        lambda *a, **k: (list(items), list(failed)),
    )


def stub_fetch_raises(monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(service.client, "fetch_all_day_events", boom)


# --- the anti-flicker guarantee -------------------------------------------

def test_version_bumps_when_events_change(monkeypatch):
    stub_fetch(monkeypatch, [make_event("A")])
    service._refresh_once(TODAY)
    v1 = service.get_snapshot().version

    stub_fetch(monkeypatch, [make_event("A"), make_event("B")])
    service._refresh_once(TODAY)
    assert service.get_snapshot().version > v1


def test_version_does_not_bump_on_identical_payload(monkeypatch):
    """A 30-min poll returning the same events must not touch the panel."""
    stub_fetch(monkeypatch, [make_event("A")])
    service._refresh_once(TODAY)
    v1 = service.get_snapshot().version

    service._refresh_once(TODAY)
    service._refresh_once(TODAY)
    assert service.get_snapshot().version == v1


def test_fetched_at_advances_without_bumping_version(monkeypatch):
    stub_fetch(monkeypatch, [make_event("A")])
    service._refresh_once(TODAY)
    snap1 = service.get_snapshot()

    service._refresh_once(TODAY)
    snap2 = service.get_snapshot()
    assert snap2.version == snap1.version
    assert snap2.fetched_at >= snap1.fetched_at


# --- failure handling ------------------------------------------------------

def test_transient_failure_keeps_last_good_events(monkeypatch):
    stub_fetch(monkeypatch, [make_event("A")])
    service._refresh_once(TODAY)
    good = service.get_snapshot()

    stub_fetch_raises(monkeypatch, OSError("network down"))
    service._refresh_once(TODAY)
    snap = service.get_snapshot()
    assert snap.status == service.OK
    assert snap.events == good.events
    assert snap.error is not None


def test_auth_error_reports_auth_required(monkeypatch):
    def bad():
        raise AuthError("no token")
    monkeypatch.setattr(service, "load_credentials", bad)
    service._refresh_once(TODAY)
    assert service.get_snapshot().status == service.AUTH_REQUIRED


def test_auth_error_does_not_clobber_last_good_events(monkeypatch):
    stub_fetch(monkeypatch, [make_event("A")])
    service._refresh_once(TODAY)

    def bad():
        raise AuthError("revoked")
    monkeypatch.setattr(service, "load_credentials", bad)
    service._refresh_once(TODAY)
    assert len(service.get_snapshot().events) == 1


def test_all_calendars_failed_is_a_failure(monkeypatch):
    stub_fetch(monkeypatch, [], failed=[{"id": "cal", "name": "Cal", "primary": True}])
    service._refresh_once(TODAY)
    snap = service.get_snapshot()
    assert snap.status != service.OK or snap.error


def test_secondary_calendar_failure_publishes_partial(monkeypatch):
    service._calendars = [
        {"id": "p", "name": "Primary", "primary": True},
        {"id": "s", "name": "Shared", "primary": False},
    ]
    stub_fetch(monkeypatch, [make_event("A")],
               failed=[{"id": "s", "name": "Shared", "primary": False}])
    service._refresh_once(TODAY)
    snap = service.get_snapshot()
    assert snap.status == service.OK and snap.partial


def test_primary_calendar_failure_is_not_published(monkeypatch):
    """Showing the day without your main calendar is worse than being stale."""
    service._calendars = [
        {"id": "p", "name": "Primary", "primary": True},
        {"id": "s", "name": "Shared", "primary": False},
    ]
    stub_fetch(monkeypatch, [make_event("A")],
               failed=[{"id": "p", "name": "Primary", "primary": True}])
    service._refresh_once(TODAY)
    assert service.get_snapshot().events == ()


def test_boot_grace_reports_loading_not_error(monkeypatch):
    """No RTC on a Pi: the clock and network are not up for the first minute."""
    import time
    service._started_at = time.time()
    stub_fetch_raises(monkeypatch, OSError("no route to host"))
    service._refresh_once(TODAY)
    assert service.get_snapshot().status == service.LOADING


# --- staleness -------------------------------------------------------------

def test_staleness_is_derived_from_age():
    snap = service.Snapshot(status=service.OK, fetched_at=1000.0)
    assert not snap.is_stale(now=1000.0 + config.STALE_AFTER_SECONDS - 1)
    assert snap.is_stale(now=1000.0 + config.STALE_AFTER_SECONDS + 1)


# --- cache -----------------------------------------------------------------

def test_cache_round_trip():
    cache.save(TODAY, [make_event("A")])
    assert cache.load(TODAY)[0]["title"] == "A"


def test_cache_from_another_day_is_discarded():
    """Yesterday's all-day events shown as today's is worse than showing none."""
    cache.save(date(2026, 9, 11), [make_event("A")])
    assert cache.load(TODAY) is None


def test_corrupt_cache_returns_none():
    config.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.CACHE_FILE.write_text("{ not json")
    assert cache.load(TODAY) is None


def test_cache_write_is_atomic_and_leaves_no_tmp():
    cache.save(TODAY, [make_event("A")])
    assert not list(config.CACHE_FILE.parent.glob("*.tmp"))
    assert json.loads(config.CACHE_FILE.read_text())["day"] == TODAY.isoformat()
