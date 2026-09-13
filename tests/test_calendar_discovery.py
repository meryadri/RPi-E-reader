"""
Calendar discovery tests.

Deliberately a separate module from test_calendar_service.py: that file's autouse
fixture stubs client.list_calendars module-wide, which would shadow the very
function under test here.
"""
from integrations.google_calendar import client, config


# --- calendar discovery ----------------------------------------------------

class FakeCalendars:
    """Minimal stand-in for the calendars()/calendarList() API surfaces."""

    def __init__(self, listed=(), meta=None, shared=()):
        self._listed = list(listed)
        self._meta = meta or {}
        self._shared = set(shared)

    # service.calendars().get(calendarId=...).execute()
    def calendars(self):
        outer = self

        class _C:
            def get(self, calendarId):
                class _R:
                    def execute(_s):
                        if calendarId not in outer._shared:
                            raise RuntimeError("404 notFound")
                        return {"summary": outer._meta.get(calendarId, calendarId)}
                return _R()
        return _C()

    # service.calendarList().list(...).execute()
    def calendarList(self):
        outer = self

        class _CL:
            def list(self, maxResults=None, pageToken=None):
                class _R:
                    def execute(_s):
                        return {"items": outer._listed}
                return _R()
        return _CL()


def test_configured_ids_come_first_and_first_is_primary(monkeypatch):
    monkeypatch.setattr(config, "calendar_ids", lambda: ["me@gmail.com", "team@group.calendar.google.com"])
    svc = FakeCalendars(
        shared=["me@gmail.com", "team@group.calendar.google.com"],
        meta={"me@gmail.com": "Personal", "team@group.calendar.google.com": "Team"},
    )
    cals = client.list_calendars(svc)
    assert [c["id"] for c in cals] == ["me@gmail.com", "team@group.calendar.google.com"]
    assert cals[0]["primary"] and not cals[1]["primary"]


def test_unshared_configured_id_is_skipped_not_fatal(monkeypatch):
    monkeypatch.setattr(config, "calendar_ids", lambda: ["ok@gmail.com", "nope@gmail.com"])
    svc = FakeCalendars(shared=["ok@gmail.com"], meta={"ok@gmail.com": "OK"})
    cals = client.list_calendars(svc)
    assert [c["id"] for c in cals] == ["ok@gmail.com"]


def test_discovered_calendars_merge_without_duplicates(monkeypatch):
    monkeypatch.setattr(config, "calendar_ids", lambda: ["me@gmail.com"])
    svc = FakeCalendars(
        shared=["me@gmail.com"],
        meta={"me@gmail.com": "Personal"},
        listed=[
            {"id": "me@gmail.com", "summary": "Personal"},      # already configured
            {"id": "other@group.calendar.google.com", "summary": "Other"},
        ],
    )
    cals = client.list_calendars(svc)
    assert [c["id"] for c in cals] == ["me@gmail.com", "other@group.calendar.google.com"]


def test_free_busy_only_calendar_is_dropped(monkeypatch):
    """Those return events with no title at all."""
    monkeypatch.setattr(config, "calendar_ids", lambda: [])
    svc = FakeCalendars(listed=[
        {"id": "a@x", "summary": "Readable", "accessRole": "reader"},
        {"id": "b@x", "summary": "Busy only", "accessRole": "freeBusyReader"},
    ])
    assert [c["id"] for c in client.list_calendars(svc)] == ["a@x"]


def test_discovery_only_still_marks_a_primary(monkeypatch):
    monkeypatch.setattr(config, "calendar_ids", lambda: [])
    svc = FakeCalendars(listed=[{"id": "a@x", "summary": "Only"}])
    cals = client.list_calendars(svc)
    assert cals[0]["primary"]
