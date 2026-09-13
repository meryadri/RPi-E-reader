"""
Google Calendar API calls.

I/O only — every decision about what an event *means* lives in events.py, so
that logic can be tested without a network or credentials.
"""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from . import config, events

# A page cap so a server-side bug cannot spin the worker thread forever.
_MAX_PAGES = 20
_PAGE_SIZE = 250


def build_service(creds):
    """Build the Calendar v3 client."""
    import httplib2
    import google_auth_httplib2
    from googleapiclient.discovery import build

    # The timeout is the important part: httplib2 defaults to *no* timeout, so
    # a half-open TCP connection on flaky Wi-Fi would hang the worker thread
    # forever.  Python cannot kill a thread, so without this the dashboard
    # freezes on "Checking calendar..." until someone reboots the Pi.
    http = google_auth_httplib2.AuthorizedHttp(
        creds, http=httplib2.Http(timeout=config.HTTP_TIMEOUT_SECONDS)
    )
    # static_discovery uses the bundled discovery document instead of fetching
    # it over HTTP, so building the client during app setup cannot block on a
    # boot with no network yet.
    return build(
        "calendar", "v3", http=http,
        cache_discovery=False, static_discovery=True,
    )


def list_calendars(service) -> list[dict]:
    """Every subscribed calendar, primary first.

    Primary-first ordering matters: it decides which copy of a duplicated event
    survives dedupe.
    """
    found: list[dict] = []
    page_token = None

    for _ in range(_MAX_PAGES):
        # showDeleted/showHidden both default to False, which is what we want.
        resp = service.calendarList().list(
            maxResults=_PAGE_SIZE, pageToken=page_token
        ).execute()

        for entry in resp.get("items", []):
            cal_id = entry.get("id")
            if not cal_id:
                continue
            name = entry.get("summaryOverride") or entry.get("summary") or cal_id

            # freeBusyReader access returns events with no summary at all, so
            # including these calendars renders a column of "(no title)".
            if entry.get("accessRole") == "freeBusyReader":
                continue
            if cal_id in config.EXCLUDE_CALENDAR_IDS:
                continue
            if any(s in name.lower() for s in config.EXCLUDE_CALENDAR_NAME_SUBSTRINGS):
                continue

            found.append(
                {"id": cal_id, "name": name, "primary": bool(entry.get("primary"))}
            )

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # NOTE: deliberately not filtering on `selected`.  It is false-by-default
    # and often absent, so filtering on it silently drops real calendars.
    found.sort(key=lambda c: (not c["primary"], c["name"].casefold()))
    return found


def list_events(service, calendar_id: str, time_min: str, time_max: str) -> list[dict]:
    """Raw events.list items for one calendar."""
    items: list[dict] = []
    page_token = None

    for _ in range(_MAX_PAGES):
        # singleEvents=True makes Google expand recurring events server-side.
        # Without it we would get a recurrence master with an RRULE and have to
        # implement RRULE/EXDATE/RECURRENCE-ID ourselves — which for all-day
        # events means every birthday and anniversary.
        #
        # Deliberately NOT using syncToken: incremental sync is invalidated
        # whenever timeMin/timeMax change, and ours change every midnight.
        resp = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,        # orderBy=startTime is only legal with this
            orderBy="startTime",
            showDeleted=False,
            maxResults=_PAGE_SIZE,
            pageToken=page_token,
        ).execute()

        items.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return items


def fetch_all_day_events(
    service, calendars: list[dict], day: date
) -> tuple[list[dict], list[dict]]:
    """All-day events covering `day`, merged across calendars.

    Returns (events, failed_calendars).  Each calendar is fetched
    independently so one broken or unshared calendar degrades to "skip it"
    rather than losing the whole refresh.
    """
    tz = ZoneInfo(config.TIMEZONE)
    time_min, time_max = events.window_bounds(day, tz)

    collected: list[dict] = []
    failed: list[dict] = []

    for cal in calendars:
        try:
            raw = list_events(service, cal["id"], time_min, time_max)
        except Exception as exc:
            # A 404 means the calendar was unsubscribed between listing it and
            # querying it — not worth reporting as a failure.
            if "404" in str(exc) or "notFound" in str(exc):
                continue
            failed.append(cal)
            continue

        for item in raw:
            if not events.is_all_day(item):
                continue
            if not events.keep(
                item,
                day,
                include_birthdays=config.INCLUDE_BIRTHDAYS,
                hide_declined=config.HIDE_DECLINED,
            ):
                continue
            collected.append(events.normalize(item, cal["id"], cal["name"], day))

    collected = events.dedupe(collected)
    collected.sort(key=events.sort_key)
    return collected, failed
