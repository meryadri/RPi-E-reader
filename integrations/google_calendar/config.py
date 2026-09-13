"""
Tunables for the Google Calendar integration.

Everything here is overridable by environment variable so the Pi can differ from
the laptop without a code change.
"""
from __future__ import annotations
import os
from pathlib import Path

# --- Paths ------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
# Repo root: integrations/google_calendar/config.py → parents[2]
_ROOT = _HERE.parents[1]

SECRETS_DIR = Path(os.environ.get("GCAL_SECRETS_DIR", _HERE / "secrets"))
CREDENTIALS_FILE = SECRETS_DIR / "credentials.json"
TOKEN_FILE = SECRETS_DIR / "token.json"

CACHE_FILE = _ROOT / "data" / "calendar_cache.json"

# --- Auth -------------------------------------------------------------------

# Read-only: this integration can never modify your calendar.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# --- Time zone --------------------------------------------------------------

# Set explicitly rather than trusting the system clock.  A freshly imaged
# Raspberry Pi OS runs on UTC until `timedatectl set-timezone` is run, which
# would roll the dashboard over to "tomorrow" at 8pm Eastern — and would work
# perfectly on the laptop, so you would never catch it in the simulator.
TIMEZONE = os.environ.get("GCAL_TZ", "America/New_York")

# --- Refresh cadence --------------------------------------------------------

# All-day events are almost always created days or weeks ahead, so the interval
# only covers same-day edits.  The fetch that actually matters is the one at
# local midnight, which is triggered by a date change rather than by this.
REFRESH_SECONDS = int(os.environ.get("GCAL_REFRESH_SECONDS", 30 * 60))

# How often the worker wakes to check "has the date changed / is a refresh due".
# Cheap: no network, just a clock read.
TICK_SECONDS = 30

# Backoff after a failed fetch, so a Wi-Fi blip does not leave the panel stale
# for a full interval.  Capped at REFRESH_SECONDS.
ERROR_BACKOFF_SECONDS = (30, 60, 120, 300)

# A revoked or expired token will not fix itself; retry hourly rather than
# hammering Google every 30 seconds.
AUTH_ERROR_BACKOFF_SECONDS = 60 * 60

# Data older than this is rendered with an "as of HH:MM" marker.  Derived on
# read, so it also catches a worker thread that died or hung.
STALE_AFTER_SECONDS = int(os.environ.get("GCAL_STALE_AFTER", 45 * 60))

# --- Network ----------------------------------------------------------------

# Without a timeout, a half-open TCP connection on flaky Wi-Fi hangs the worker
# thread forever.  Python cannot kill a thread, so this is the only defence
# between a dropped packet and a dashboard frozen until reboot.
HTTP_TIMEOUT_SECONDS = 20

# --- Filtering --------------------------------------------------------------

# Birthdays are all-day, annually recurring, and usually the whole point of an
# all-day dashboard.  Set GCAL_BIRTHDAYS=0 if the list gets long.
INCLUDE_BIRTHDAYS = os.environ.get("GCAL_BIRTHDAYS", "1") != "0"

# Events you have explicitly declined are hidden by default.
HIDE_DECLINED = os.environ.get("GCAL_HIDE_DECLINED", "1") != "0"

# Calendars to leave out entirely — by id, or by a case-insensitive substring of
# the calendar's name.  Useful when a holiday calendar floods the panel.
EXCLUDE_CALENDAR_IDS: set[str] = set(
    filter(None, os.environ.get("GCAL_EXCLUDE_IDS", "").split(","))
)
EXCLUDE_CALENDAR_NAME_SUBSTRINGS: list[str] = [
    s.strip().lower()
    for s in os.environ.get("GCAL_EXCLUDE_NAMES", "").split(",")
    if s.strip()
]
