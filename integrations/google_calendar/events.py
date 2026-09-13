"""
Pure event logic — no network, no credentials, no Google client objects.

Everything here takes plain dicts shaped like Google Calendar API v3
`events.list` items and returns plain dicts, so all of the date arithmetic is
unit-testable offline.  That is deliberate: this module is where the bugs would
live, so it is the part that has to be cheap to test.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# eventType values that are all-day but are pure noise on a dashboard.
#
# "workingLocation" is the one that matters: Google Calendar auto-creates one of
# these per weekday on your primary calendar, so without this filter "Office" or
# "Home" would be the top row of the dashboard every single working day.
NOISE_EVENT_TYPES = frozenset({"workingLocation"})

NO_TITLE = "(no title)"

# The dashboard only has room for a two-line subtitle; the cap keeps a pasted
# meeting agenda out of the cached JSON and out of the snapshot equality check.
MAX_DESCRIPTION_CHARS = 200

# Descriptions written in the Google Calendar web UI are HTML, not plain text.
_BREAK_RE = re.compile(r"(?i)<(?:br|/p|/div|/li|/tr)\s*/?>")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_description(raw: str | None) -> str:
    """Flatten a calendar description into one line of plain text.

    Line breaks become spaces rather than being preserved: the card wraps the
    text itself, and an event's own newlines would otherwise waste both of the
    two available subtitle lines on a single short sentence.
    """
    if not raw:
        return ""
    text = _BREAK_RE.sub(" ", raw)
    text = _TAG_RE.sub("", text)
    # After tag removal, so a literal "&lt;b&gt;" in the text is not then
    # treated as markup.
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > MAX_DESCRIPTION_CHARS:
        text = text[:MAX_DESCRIPTION_CHARS].rstrip() + "..."
    return text


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def is_all_day(event: dict) -> bool:
    """True for an all-day event.

    Google marks the distinction by which key is present: an all-day event has
    start.date ("2026-09-12"), a timed one has start.dateTime.  That is the
    whole test.
    """
    return "date" in (event.get("start") or {})


def parse_dt(value: str) -> datetime:
    """Parse an RFC3339 timestamp into an aware datetime."""
    # fromisoformat only accepts a trailing "Z" from Python 3.11; Raspberry Pi
    # OS Bullseye ships 3.9.  One replace keeps this working everywhere.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def all_day_span(event: dict) -> tuple[date, date] | None:
    """Return (start, end_exclusive) for an all-day event, or None.

    Google's end.date is *exclusive*: a one-day event on the 12th is
    start.date=2026-09-12, end.date=2026-09-13.
    """
    if not is_all_day(event):
        return None
    try:
        start = date.fromisoformat(event["start"]["date"])
    except (KeyError, TypeError, ValueError):
        return None

    raw_end = (event.get("end") or {}).get("date")
    end = None
    if raw_end:
        try:
            end = date.fromisoformat(raw_end)
        except (TypeError, ValueError):
            end = None

    # Two defensive clamps, both of which have been seen in the wild on events
    # imported from third-party ICS feeds and Outlook syncs:
    #   - end.date missing entirely
    #   - end.date == start.date (a "zero-length" all-day event)
    # Without this, "start <= today < end" is vacuously false and a real event
    # on your calendar silently never appears, with nothing to debug.
    if end is None or end <= start:
        end = start + timedelta(days=1)

    return start, end


def covers_day(event: dict, day: date) -> bool:
    """True if an all-day event covers `day`.

    Because end is exclusive, `start <= day < end` handles single-day and
    multi-day events uniformly.  Writing it as `day <= end` would show every
    event one day too long.
    """
    span = all_day_span(event)
    if span is None:
        return False
    start, end = span
    return start <= day < end


def covers_day_timed(event: dict, day: date, tz: ZoneInfo) -> bool:
    """True if a timed event overlaps `day` in local time."""
    try:
        start = parse_dt(event["start"]["dateTime"])
        end = parse_dt(event["end"]["dateTime"])
    except (KeyError, TypeError, ValueError):
        return False
    day_start = datetime.combine(day, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    # Overlap, so an event running 23:00 yesterday -> 01:00 today counts.
    return start < day_end and end > day_start


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def is_cancelled(event: dict) -> bool:
    return event.get("status") == "cancelled"


def is_declined_by_self(event: dict) -> bool:
    """True only if *you* declined.

    `attendees` is absent on most events (no guests at all, or maxAttendees
    exceeded), hence the .get default.  Only the entry flagged `self` counts —
    someone else declining is not a reason to hide the event from you.
    """
    for attendee in event.get("attendees") or []:
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return True
    return False


def is_noise(event: dict, include_birthdays: bool = True) -> bool:
    """True if this event should never reach the dashboard."""
    event_type = event.get("eventType", "default")
    if event_type in NOISE_EVENT_TYPES:
        return True
    if event_type == "birthday" and not include_birthdays:
        return True
    return False


def keep(
    event: dict,
    day: date,
    *,
    include_birthdays: bool = True,
    hide_declined: bool = True,
) -> bool:
    """Whether an all-day event survives every filter for `day`."""
    if is_cancelled(event):
        return False
    if is_noise(event, include_birthdays):
        return False
    if hide_declined and is_declined_by_self(event):
        return False
    return covers_day(event, day)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalize(event: dict, calendar_id: str, calendar_name: str, day: date) -> dict:
    """Build the dict the dashboard renders.

    Every key is always present with a str/int/bool value.  The render path has
    no try/except above it in `display/runtime.py`, so a None leaking through
    here would crash the whole process, not just the calendar column.
    """
    span = all_day_span(event)
    if span is None:
        start = end = day
        days_total, day_index = 1, 0
    else:
        start, end = span
        days_total = (end - start).days
        day_index = (day - start).days

    title = (event.get("summary") or "").strip() or NO_TITLE
    description = clean_description(event.get("description"))

    return {
        "id": f"{calendar_id}:{event.get('id', '')}",
        "ical_uid": event.get("iCalUID", ""),
        "title": title,
        "description": description,
        "all_day": True,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),     # exclusive, verbatim from Google
        "days_total": max(1, days_total),
        "day_index": max(0, day_index),
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "event_type": event.get("eventType", "default"),
    }


def sort_key(item: dict) -> tuple:
    """A deterministic *total* order.

    Determinism is not cosmetic here: the refresh loop only redraws the e-ink
    panel when the rendered payload differs from the last one.  If two same-day
    events could swap places between refreshes, the panel would do a full
    refresh every cycle forever.  Ties break on id, never on dict order.
    """
    return (
        item["start_date"],
        -item["days_total"],          # longer spans first
        item["title"].casefold(),
        item["id"],
    )


def dedupe(items: list[dict]) -> list[dict]:
    """Drop the same event appearing on more than one calendar.

    An invite shows up both on your primary calendar and on the organiser's
    calendar if you subscribe to it.  iCalUID is stable across those copies, but
    with singleEvents=True it identifies the *series*, so the key has to include
    the date or every occurrence of a recurring event would collapse into one.

    Input order decides the winner, so callers should pass primary first.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for item in items:
        uid = item.get("ical_uid") or item["id"]
        key = (uid, item["start_date"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Query window
# ---------------------------------------------------------------------------

def window_bounds(day: date, tz: ZoneInfo) -> tuple[str, str]:
    """RFC3339 (timeMin, timeMax) for a one-day query, widened by a day each side.

    events.list filters on overlap — timeMin bounds an event's end, timeMax
    bounds its start — so a fortnight-long holiday that began last week is still
    returned for a today-only window.

    We widen anyway and re-check with covers_day() locally, because date-only
    events are resolved in *each calendar's* own time zone.  A subscribed
    calendar in another zone has its all-day boundaries evaluated against a
    different offset than ours, which makes boundary events appear and vanish
    unpredictably.  Widening costs nothing (same one request per calendar) and
    cannot drop an event, since a longer window is strictly more permissive.
    """
    lo = datetime.combine(day - timedelta(days=1), time.min, tzinfo=tz)
    hi = datetime.combine(day + timedelta(days=2), time.min, tzinfo=tz)
    # isoformat() on an aware datetime includes the offset.  A naive datetime
    # would produce no offset and the API would answer HTTP 400.
    return lo.isoformat(), hi.isoformat()
