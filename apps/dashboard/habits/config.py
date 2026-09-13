"""
Habit checklist configuration.

Nothing here is secret, but everything it points at is: the habit list and the
completion log live in private/, which is gitignored wholesale.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

# Repo root: apps/dashboard/habits/config.py → parents[3]
_ROOT = Path(__file__).resolve().parents[3]

PRIVATE_DIR = Path(os.environ.get("HABITS_DIR", _ROOT / "private"))
HABITS_FILE = PRIVATE_DIR / "habits.json"
LOG_FILE = PRIVATE_DIR / "habit_log.json"
TOKEN_FILE = PRIVATE_DIR / "habit_token.txt"

PORT = int(os.environ.get("HABITS_PORT", 3004))

# The hour a new habit-day begins.  Ticking something at 1am means you are
# finishing today, not starting tomorrow — without this a late night would
# silently split across two days and break a streak.
ROLLOVER_HOUR = int(os.environ.get("HABIT_ROLLOVER_HOUR", 4))

# How many calendar months the history page shows.
HEATMAP_MONTHS = int(os.environ.get("HABIT_HEATMAP_MONTHS", 6))

# How often the service checks whether the habit-day has rolled over.
TICK_SECONDS = 30


def habit_day(now: datetime | None = None) -> date:
    """The day a tick at `now` belongs to.

    The single definition of "today" for the panel, the web page, the log key and
    every streak calculation.  If anything else grew its own idea of the current
    day, a tick at 1am would be recorded under one date and counted under
    another.

    Deliberately different from google_calendar.today(), which is a strict
    calendar day because calendar events genuinely change at midnight.
    """
    now = datetime.now() if now is None else now
    return (now - timedelta(hours=ROLLOVER_HOUR)).date()
