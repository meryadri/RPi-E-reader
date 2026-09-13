"""
Credentials for the Google Calendar API (read-only).

Two modes, tried in this order:

1. **Service account** (default) — drop a key JSON at secrets/service_account.json
   and share each calendar with its client_email address.  No consent screen, no
   browser, and nothing that expires.

2. **OAuth installed-app** (fallback) — needs a published OAuth consent screen,
   which Google only allows with a domain you can verify in Search Console.

See README.md in this directory.
"""
from __future__ import annotations

import json
import os
import sys

from . import config


class AuthError(Exception):
    """Credentials are missing, revoked, or expired beyond refresh."""


def mode() -> str:
    """Which auth mode is configured: 'service_account', 'oauth', or 'none'."""
    if config.SERVICE_ACCOUNT_FILE.exists():
        return "service_account"
    if config.TOKEN_FILE.exists():
        return "oauth"
    return "none"


def service_account_email() -> str | None:
    """The address calendars must be shared with, read from the key file."""
    try:
        with open(config.SERVICE_ACCOUNT_FILE) as f:
            return json.load(f).get("client_email")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Service account
# ---------------------------------------------------------------------------

def _load_service_account():
    try:
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - dependency not installed
        raise AuthError(f"Google libraries not installed: {exc}") from exc

    try:
        return service_account.Credentials.from_service_account_file(
            str(config.SERVICE_ACCOUNT_FILE), scopes=config.SCOPES
        )
    except Exception as exc:
        raise AuthError(f"Bad service account key: {exc}") from exc


# ---------------------------------------------------------------------------
# OAuth installed-app
# ---------------------------------------------------------------------------

def _write_token(creds) -> None:
    """Persist credentials as 0600 — the default 0644 is sloppy for a token."""
    config.SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(config.TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())


def _load_oauth():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google.auth.exceptions import GoogleAuthError
    except ImportError as exc:  # pragma: no cover - dependency not installed
        raise AuthError(f"Google libraries not installed: {exc}") from exc

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
            raise AuthError(f"Token refresh failed: {exc}") from exc
        _write_token(creds)
        return creds

    raise AuthError("Token has no refresh token. Re-run the consent flow.")


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def load_credentials():
    """Return usable credentials, or raise AuthError.

    Raises rather than returning None so the caller can tell "no calendar is
    connected" apart from "the network is down" — those need different messages
    on the dashboard.
    """
    kind = mode()
    if kind == "service_account":
        return _load_service_account()
    if kind == "oauth":
        return _load_oauth()
    raise AuthError(
        f"No credentials at {config.SERVICE_ACCOUNT_FILE}. "
        "See integrations/google_calendar/README.md"
    )


def bootstrap() -> None:
    """Run the interactive OAuth consent flow (fallback mode only)."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit("google-auth-oauthlib is not installed. Run: pip install -r requirements.txt")

    if not config.CREDENTIALS_FILE.exists():
        sys.exit(
            f"Missing {config.CREDENTIALS_FILE}\n\n"
            "This is the OAuth fallback, which needs a published consent screen.\n"
            "The default setup uses a service account instead — see\n"
            "integrations/google_calendar/README.md"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.CREDENTIALS_FILE), config.SCOPES
    )
    # prompt=consent is not optional: if you have already consented to this
    # client, Google returns an access token with no refresh token, and the Pi
    # dies silently an hour later with nothing to go on.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    _write_token(creds)
    print(f"\nWrote {config.TOKEN_FILE}")
