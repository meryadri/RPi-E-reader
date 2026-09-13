"""
Pure logic tests for the Google Calendar integration.

No network, no credentials, no Google libraries — everything here runs against
hand-written dicts shaped like events.list items.
"""
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from integrations.google_calendar import events as ev

TODAY = date(2026, 9, 12)
NY = ZoneInfo("America/New_York")


def all_day(start, end=None, **extra):
    e = {"id": "e1", "summary": "Thing", "start": {"date": start}}
    if end is not None:
        e["end"] = {"date": end}
    e.update(extra)
    return e


def timed(start, end, **extra):
    e = {"id": "t1", "summary": "Meeting",
         "start": {"dateTime": start}, "end": {"dateTime": end}}
    e.update(extra)
    return e


# --- classification --------------------------------------------------------

def test_all_day_vs_timed():
    assert ev.is_all_day(all_day("2026-09-12", "2026-09-13"))
    assert not ev.is_all_day(
        timed("2026-09-12T09:00:00-04:00", "2026-09-12T10:00:00-04:00")
    )


def test_trailing_z_parses():
    """fromisoformat only accepts 'Z' from 3.11; Pi OS Bullseye ships 3.9."""
    assert ev.parse_dt("2026-09-12T09:00:00Z").tzinfo is not None


# --- the exclusive end date ------------------------------------------------

def test_single_day_event_covers_only_its_own_day():
    e = all_day("2026-09-12", "2026-09-13")
    assert ev.covers_day(e, TODAY)
    assert not ev.covers_day(e, date(2026, 9, 13))
    assert not ev.covers_day(e, date(2026, 9, 11))


def test_end_date_equal_to_today_is_excluded():
    """end is exclusive, so this event's last day was yesterday."""
    assert not ev.covers_day(all_day("2026-09-11", "2026-09-12"), TODAY)


def test_event_starting_tomorrow_is_excluded():
    assert not ev.covers_day(all_day("2026-09-13", "2026-09-14"), TODAY)


def test_multi_day_event_spanning_today():
    e = all_day("2026-09-09", "2026-09-13")
    assert ev.covers_day(e, TODAY)
    n = ev.normalize(e, "cal", "Cal", TODAY)
    assert (n["day_index"], n["days_total"]) == (3, 4)


def test_missing_end_date_treated_as_one_day():
    assert ev.covers_day(all_day("2026-09-12"), TODAY)


def test_zero_length_event_still_shows():
    """An ICS import can produce end == start; naive logic hides it forever."""
    assert ev.covers_day(all_day("2026-09-12", "2026-09-12"), TODAY)


def test_end_before_start_is_clamped_not_crashed():
    assert ev.covers_day(all_day("2026-09-12", "2026-09-10"), TODAY)


def test_malformed_date_does_not_raise():
    assert ev.all_day_span(all_day("not-a-date")) is None
    assert not ev.covers_day(all_day("not-a-date"), TODAY)


# --- filtering -------------------------------------------------------------

def test_cancelled_excluded():
    assert not ev.keep(all_day("2026-09-12", "2026-09-13", status="cancelled"), TODAY)


def test_declined_by_self_excluded_but_not_by_others():
    mine = all_day("2026-09-12", "2026-09-13",
                   attendees=[{"self": True, "responseStatus": "declined"}])
    theirs = all_day("2026-09-12", "2026-09-13",
                     attendees=[{"email": "x@y.z", "responseStatus": "declined"}])
    assert not ev.keep(mine, TODAY)
    assert ev.keep(theirs, TODAY)
    assert ev.keep(mine, TODAY, hide_declined=False)


def test_attendees_absent_is_fine():
    assert ev.keep(all_day("2026-09-12", "2026-09-13"), TODAY)


def test_working_location_excluded():
    """Google auto-creates one of these per weekday on the primary calendar."""
    e = all_day("2026-09-12", "2026-09-13", eventType="workingLocation",
                summary="Office")
    assert not ev.keep(e, TODAY)


def test_birthdays_kept_by_default_and_hideable():
    e = all_day("2026-09-12", "2026-09-13", eventType="birthday")
    assert ev.keep(e, TODAY)
    assert not ev.keep(e, TODAY, include_birthdays=False)


def test_tentative_and_transparent_kept():
    """Holidays and birthdays are all transparent; filtering them would delete
    exactly the events this feature exists to show."""
    assert ev.keep(
        all_day("2026-09-12", "2026-09-13", status="tentative",
                transparency="transparent"),
        TODAY,
    )


# --- normalisation ---------------------------------------------------------

def test_missing_summary_gets_placeholder():
    e = {"id": "x", "start": {"date": "2026-09-12"}, "end": {"date": "2026-09-13"}}
    assert ev.normalize(e, "cal", "Cal", TODAY)["title"] == ev.NO_TITLE


def test_normalize_always_returns_complete_dict():
    """render() has no try/except above it — a missing key is a dead panel."""
    n = ev.normalize(all_day("2026-09-12", "2026-09-13"), "cal", "Cal", TODAY)
    for key in ("id", "title", "all_day", "start_date", "end_date",
                "days_total", "day_index", "calendar_id", "calendar_name"):
        assert n[key] is not None


# --- ordering and dedupe ---------------------------------------------------

def _norm(uid, title, start="2026-09-12", end="2026-09-13", cal="a"):
    e = all_day(start, end, summary=title, iCalUID=uid)
    e["id"] = f"{uid}-{cal}"
    return ev.normalize(e, cal, cal, TODAY)


def test_dedupe_across_calendars_keeps_first():
    items = [_norm("u1", "Trip", cal="primary"), _norm("u1", "Trip", cal="shared")]
    out = ev.dedupe(items)
    assert len(out) == 1 and out[0]["calendar_id"] == "primary"


def test_dedupe_keeps_separate_occurrences_of_a_series():
    """Key is (uid, date) — otherwise every birthday collapses into one."""
    items = [_norm("u1", "B", "2026-09-12", "2026-09-13"),
             _norm("u1", "B", "2026-09-14", "2026-09-15")]
    assert len(ev.dedupe(items)) == 2


def test_sort_is_a_deterministic_total_order():
    """Non-determinism here would full-refresh the panel every cycle forever."""
    import random
    items = [_norm(f"u{i}", t) for i, t in enumerate(["b", "a", "c", "a"])]
    expected = sorted(items, key=ev.sort_key)
    for _ in range(20):
        shuffled = items[:]
        random.shuffle(shuffled)
        assert sorted(shuffled, key=ev.sort_key) == expected


# --- query window ----------------------------------------------------------

def test_window_includes_utc_offset():
    """A naive datetime yields no offset and the API answers HTTP 400."""
    lo, hi = ev.window_bounds(TODAY, NY)
    assert lo.endswith("-04:00") and hi.endswith("-04:00")


def test_window_is_widened_by_a_day_each_side():
    lo, hi = ev.window_bounds(TODAY, NY)
    assert lo.startswith("2026-09-11T00:00:00")
    assert hi.startswith("2026-09-14T00:00:00")


@pytest.mark.parametrize("day", [date(2026, 3, 8), date(2026, 11, 1)])
def test_window_survives_dst_transitions(day):
    lo, hi = ev.window_bounds(day, NY)
    assert lo[-6:] != hi[-6:]   # the offset changes across the boundary
