"""
Streak and consistency maths — pure, no file I/O, no Flask.

All the fiddly date logic lives here so it can be tested offline, the same split
that made integrations/google_calendar/events.py tractable.

Every function takes the log as {"YYYY-MM-DD": [habit names]} and a `today`
which the caller must obtain from config.habit_day() — never from date.today().
"""
from __future__ import annotations

from datetime import date, timedelta


def _did(log: dict[str, list[str]], habit: str, day: date) -> bool:
    return habit in log.get(day.isoformat(), [])


def is_workday(day: date) -> bool:
    """Mon-Fri.  Saturday and Sunday are neutral for streaks."""
    return day.weekday() < 5


def prev_workday(day: date) -> date:
    day -= timedelta(days=1)
    while not is_workday(day):
        day -= timedelta(days=1)
    return day


def next_workday(day: date) -> date:
    day += timedelta(days=1)
    while not is_workday(day):
        day += timedelta(days=1)
    return day


def current_streak(log: dict[str, list[str]], habit: str, today: date) -> int:
    """Consecutive *weekdays* the habit was done, counting back from now.

    Weekends are neutral: a missed Saturday never breaks a streak, and a
    completed Saturday never extends one.  Friday then Monday is an unbroken
    run of two.

    The anchor allows for today not being ticked yet — a streak that read 0
    every morning until you ticked would be useless as a motivator.  That grace
    does not extend past the day itself: by Saturday, Friday's chance has gone,
    so a missed Friday does break the run.
    """
    if is_workday(today) and _did(log, habit, today):
        anchor = today
    else:
        anchor = prev_workday(today)

    if not _did(log, habit, anchor):
        return 0

    count = 0
    day = anchor
    while _did(log, habit, day):
        count += 1
        day = prev_workday(day)
    return count


def longest_streak(log: dict[str, list[str]], habit: str) -> int:
    """The longest run of consecutive weekdays ever recorded.

    Weekend entries are ignored entirely, so a Friday/Monday pair counts as a
    run of two rather than being broken by the weekend.
    """
    days = sorted(
        d for d in (
            date.fromisoformat(k) for k, names in log.items() if habit in names
        )
        if is_workday(d)
    )
    if not days:
        return 0

    best = run = 1
    for prev, cur in zip(days, days[1:]):
        run = run + 1 if next_workday(prev) == cur else 1
        best = max(best, run)
    return best


def completion_rate(
    log: dict[str, list[str]], habit: str, today: date, days: int
) -> float:
    """Fraction of the last `days` *weekdays* (ending today) the habit was done.

    Weekdays only, to stay consistent with the streak rule — counting weekends
    in the denominator would cap every rate at about 71% and make a perfect
    week look like a failure.
    """
    if days <= 0:
        return 0.0

    considered = hits = 0
    day = today
    while considered < days:
        if is_workday(day):
            considered += 1
            if _did(log, habit, day):
                hits += 1
        day -= timedelta(days=1)
    return hits / days


def month_grid(
    log: dict[str, list[str]], habit: str, today: date, months: int
) -> list[dict]:
    """Calendar-shaped history: one block per month, weekday-aligned.

    Returns the last `months` months, oldest first.  Each block is a dict with a
    label and exactly the cells needed for a 7-column grid:

        {"label": "Sep", "year": 2026, "cells": [{"day": ..., "state": ...}]}

    Cell states:
      "pad"    - filler before the 1st so the month starts on the right weekday
      "done"   - habit completed that day
      "miss"   - weekday that has passed and the habit was not done
      "future" - later than today; rendered faintly, not as a miss

    Each cell also carries "weekend", so Saturday and Sunday can be drawn
    differently — they never count for or against a streak.

    The leading pad is what makes this read as a calendar rather than a strip of
    squares: every column is a fixed weekday (Monday first).
    """
    blocks: list[dict] = []

    # Walk back `months - 1` whole months from the current one.
    year, month = today.year, today.month
    month -= months - 1
    while month < 1:
        month += 12
        year -= 1

    for _ in range(months):
        first = date(year, month, 1)
        if month == 12:
            next_first = date(year + 1, 1, 1)
        else:
            next_first = date(year, month + 1, 1)
        days_in_month = (next_first - first).days

        # Monday = 0, so a month starting on Wednesday gets two pad cells.
        cells: list[dict] = [
            {"day": None, "state": "pad", "weekend": False}
            for _ in range(first.weekday())
        ]
        for dom in range(1, days_in_month + 1):
            day = date(year, month, dom)
            if day > today:
                state = "future"
            elif _did(log, habit, day):
                state = "done"
            else:
                state = "miss"
            cells.append({
                "day": day, "state": state, "weekend": not is_workday(day),
            })

        blocks.append({
            "label": first.strftime("%b"),
            "year": year,
            "cells": cells,
        })

        month += 1
        if month > 12:
            month = 1
            year += 1

    return blocks


def day_progress(
    log: dict[str, list[str]], habits: list[str], today: date
) -> tuple[int, int]:
    """(completed, total) for today."""
    done = set(log.get(today.isoformat(), []))
    return sum(1 for h in habits if h in done), len(habits)


def streaks(log: dict[str, list[str]], habits: list[str], today: date) -> dict[str, int]:
    return {h: current_streak(log, h, today) for h in habits}
