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

# Google auto-creates a "workingLocation" event per weekday on the primary
# calendar; without this, "Office" is the top row every working day.
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
    """All-day events carry start.date; timed ones carry start.dateTime."""
    return "date" in (event.get("start") or {})


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

    # ICS imports and Outlook syncs produce missing or zero-length ends, which
    # would make "start <= today < end" vacuously false and hide the event.
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


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def is_cancelled(event: dict) -> bool:
    return event.get("status") == "cancelled"


def is_declined_by_self(event: dict) -> bool:
    """Only your own entry counts; someone else declining is not your problem."""
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

    Every key is always present: render() has no try/except above it, so a None
    here would take down the process, not just the calendar column.
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
    """A deterministic total order.

    The panel only redraws when the payload differs, so two events swapping
    places between refreshes would flash the screen every cycle forever.
    """
    return (
        item["start_date"],
        -item["days_total"],          # longer spans first
        item["title"].casefold(),
        item["id"],
    )


def dedupe(items: list[dict]) -> list[dict]:
    """Drop an invite that appears on both your calendar and the organiser's.

    iCalUID identifies the *series* under singleEvents=True, so the key needs
    the date too or every occurrence would collapse into one.  First wins.
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
    """RFC3339 (timeMin, timeMax), widened a day each side.

    Date-only events resolve in each calendar's own time zone, so boundary days
    appear and vanish unpredictably on a tight window.  Widening costs nothing
    and cannot drop an event; covers_day() does the exact filtering.
    """
    lo = datetime.combine(day - timedelta(days=1), time.min, tzinfo=tz)
    hi = datetime.combine(day + timedelta(days=2), time.min, tzinfo=tz)
    # A naive datetime yields no offset and the API answers HTTP 400.
    return lo.isoformat(), hi.isoformat()
