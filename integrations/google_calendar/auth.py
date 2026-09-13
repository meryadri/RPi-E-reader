"""
OAuth 2.0 installed-app flow for Google Calendar (read-only).

One-time setup runs on a machine with a browser:

    python -m integrations.google_calendar

That writes secrets/token.json, which is the only file the Pi needs — see
this package's README.md.
"""
from __future__ import annotations

import os
import sys

from . import config


class AuthError(Exception):
    """Credentials are missing, revoked, or expired beyond refresh."""


def _write_token(creds) -> None:
    """Persist credentials as 0600 — the default 0644 is sloppy for a token."""
    config.SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(config.TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())


def load_credentials():
    """Return usable credentials, or raise AuthError.

    Raises rather than returning None so the caller can tell "you never
    connected a calendar" apart from "the network is down" — those need
    different messages on the dashboard.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google.auth.exceptions import GoogleAuthError
    except ImportError as exc:  # pragma: no cover - dependency not installed
        raise AuthError(f"Google libraries not installed: {exc}") from exc

    if not config.TOKEN_FILE.exists():
        raise AuthError(
            f"No token at {config.TOKEN_FILE}. "
            "Run: python -m integrations.google_calendar"
        )

    try:
        creds = Credentials.from_authorized_user_file(
            str(config.TOKEN_FILE), config.SCOPES
        )
    except Exception as exc:
        raise AuthError(f"Could not read {config.TOKEN_FILE}: {exc}") from exc

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except GoogleAuthError as exc:
            # invalid_grant lands here: revoked access, 6 months unused, a
            # password change, or a token issued while the OAuth app was still
            # in "Testing" (those expire after 7 days).
            raise AuthError(f"Token refresh failed: {exc}") from exc
        _write_token(creds)
        return creds

    raise AuthError(
        "Token has no refresh token. Re-run: "
        "python -m integrations.google_calendar"
    )


def bootstrap() -> None:
    """Run the interactive consent flow and write token.json."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit(
            "google-auth-oauthlib is not installed.\n"
            "Run: pip install -r requirements.txt"
        )

    if not config.CREDENTIALS_FILE.exists():
        sys.exit(
            f"Missing {config.CREDENTIALS_FILE}\n\n"
            "Download the OAuth client JSON from the Google Cloud console and\n"
            "save it there. See integrations/google_calendar/README.md."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.CREDENTIALS_FILE), config.SCOPES
    )
    # access_type=offline is what asks for a refresh token at all.
    # prompt=consent is not optional in practice: if you have already consented
    # to this client, Google returns an access token with *no* refresh token,
    # and the Pi then dies silently an hour later with nothing to go on.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )
    _write_token(creds)

    print(f"\nWrote {config.TOKEN_FILE}")
    if not creds.refresh_token:
        print(
            "\nWARNING: no refresh token was issued, so this will stop working\n"
            "in about an hour. Revoke access at\n"
            "https://myaccount.google.com/permissions and run this again."
        )
    else:
        print("Copy that file to the Pi — it is the only one the Pi needs.")


def check() -> int:
    """Print what the API actually returns. The main headless debugging tool."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from . import client

    try:
        creds = load_credentials()
    except AuthError as exc:
        print(f"AUTH FAILED: {exc}")
        return 1

    service = client.build_service(creds)
    calendars = client.list_calendars(service)
    print(f"{len(calendars)} calendar(s):")
    for cal in calendars:
        print(f"  - {cal['name']}  [{cal['id']}]")

    today = datetime.now(ZoneInfo(config.TIMEZONE)).date()
    items, failed = client.fetch_all_day_events(service, calendars, today)
    print(f"\nAll-day events for {today} ({config.TIMEZONE}):")
    for item in items:
        span = (
            f"  (day {item['day_index'] + 1}/{item['days_total']})"
            if item["days_total"] > 1
            else ""
        )
        print(f"  - {item['title']}{span}   [{item['calendar_name']}]")
    if not items:
        print("  (none)")
    if failed:
        print(f"\nFailed calendars: {', '.join(c['name'] for c in failed)}")
    return 0
