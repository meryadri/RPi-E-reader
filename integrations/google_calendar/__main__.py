"""
Command-line entry point.

    python -m integrations.google_calendar --check
        Show which credentials are in use, which calendars are visible, and
        today's all-day events.  The main debugging tool — it works over SSH and
        separates "the API is broken" from "the display is broken".

    python -m integrations.google_calendar --add-calendar <calendar-id>
        Register a calendar that has been shared with the service account, so it
        is discovered automatically from now on.

    python -m integrations.google_calendar --auth
        OAuth consent flow (fallback mode only; needs a published consent
        screen).  Not required for the service-account setup.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import auth, client, config


def check() -> int:
    kind = auth.mode()
    print(f"Auth mode: {kind}")
    if kind == "service_account":
        print(f"Service account: {auth.service_account_email()}")
        print("Calendars must be shared with that address.")
    elif kind == "none":
        print(f"\nNo credentials found at {config.SERVICE_ACCOUNT_FILE}")
        print("See integrations/google_calendar/README.md")
        return 1

    try:
        creds = auth.load_credentials()
    except auth.AuthError as exc:
        print(f"\nAUTH FAILED: {exc}")
        return 1

    service = client.build_service(creds)

    try:
        calendars = client.list_calendars(service)
    except Exception as exc:
        print(f"\nCould not list calendars: {exc}")
        return 1

    print(f"\n{len(calendars)} calendar(s) visible:")
    for cal in calendars:
        flag = "  (primary)" if cal["primary"] else ""
        print(f"  - {cal['name']}{flag}\n      {cal['id']}")
    if not calendars:
        print("  (none)")
        print("\nA service account has no calendar list of its own, so each")
        print("calendar has to be named explicitly:")
        print("  python -m integrations.google_calendar --add-calendar <calendar-id>")
        print("\nFind a calendar's id in Google Calendar under")
        print("  Settings and sharing > Integrate calendar > Calendar ID")
        print("(for your main calendar it is just your Gmail address).")
        return 1

    today = datetime.now(ZoneInfo(config.TIMEZONE)).date()
    items, failed = client.fetch_all_day_events(service, calendars, today)

    print(f"\nAll-day events for {today} ({config.TIMEZONE}):")
    for item in items:
        span = (
            f"  (day {item['day_index'] + 1}/{item['days_total']})"
            if item["days_total"] > 1 else ""
        )
        print(f"  - {item['title']}{span}   [{item['calendar_name']}]")
    if not items:
        print("  (none)")
    if failed:
        print(f"\nUnreadable: {', '.join(c['name'] for c in failed)}")
    return 0


def add_calendar(calendar_id: str) -> int:
    """Confirm the calendar is readable, then record it locally.

    Deliberately does not call calendarList.insert() — that needs a write scope,
    and this integration only ever asks for calendar.readonly.
    """
    try:
        creds = auth.load_credentials()
    except auth.AuthError as exc:
        print(f"AUTH FAILED: {exc}")
        return 1

    service = client.build_service(creds)
    cal = client.get_calendar(service, calendar_id)
    if cal is None:
        print(f"Cannot read {calendar_id}")
        email = auth.service_account_email()
        if email:
            print(f"\nShare it with {email}")
            print("in Google Calendar: Settings and sharing > Share with specific")
            print("people > Add people, permission 'See all event details'.")
        return 1

    existing = _saved_ids()
    if calendar_id in existing:
        print(f"Already configured: {cal['name']}\n  {calendar_id}")
        return 0

    existing.append(calendar_id)
    config.SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.CALENDARS_FILE, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"Added: {cal['name']}\n  {calendar_id}")
    print(f"\nSaved to {config.CALENDARS_FILE}")
    return 0


def _saved_ids() -> list[str]:
    try:
        with open(config.CALENDARS_FILE) as f:
            return [c for c in json.load(f) if isinstance(c, str)]
    except Exception:
        return []


def main(argv: list[str]) -> int:
    if "--add-calendar" in argv:
        i = argv.index("--add-calendar")
        if i + 1 >= len(argv):
            print("Usage: --add-calendar <calendar-id>")
            return 2
        return add_calendar(argv[i + 1])
    if "--auth" in argv:
        auth.bootstrap()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
