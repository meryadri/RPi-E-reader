"""
Habit checklist logic — pure, offline, no Flask and no real private/ directory.
"""
from datetime import date, datetime, timedelta

import pytest

from apps.dashboard.habits import config, stats, store

TODAY = date(2026, 9, 13)


# --- the 4am rollover ------------------------------------------------------

@pytest.mark.parametrize("clock,expected", [
    ("2026-09-13 03:59", date(2026, 9, 12)),   # late night = still yesterday
    ("2026-09-13 04:00", date(2026, 9, 13)),   # the boundary itself
    ("2026-09-13 12:00", date(2026, 9, 13)),
    ("2026-09-13 23:59", date(2026, 9, 13)),
    ("2026-09-14 00:30", date(2026, 9, 13)),   # after midnight, same habit-day
])
def test_habit_day_rolls_over_at_4am(clock, expected):
    assert config.habit_day(datetime.fromisoformat(clock)) == expected


def test_rollover_hour_is_configurable(monkeypatch):
    """Proves nothing else hardcodes the boundary."""
    monkeypatch.setattr(config, "ROLLOVER_HOUR", 0)
    assert config.habit_day(datetime.fromisoformat("2026-09-13 00:30")) == date(2026, 9, 13)


# --- current streak (weekday-only) ------------------------------------------
#
# Anchors: Thu 2026-09-10, Fri 11, Sat 12, Sun 13, Mon 14, Tue 15.

THU, FRI, SAT, SUN, MON, TUE = (date(2026, 9, d) for d in (10, 11, 12, 13, 14, 15))


def days(*ds) -> dict:
    return {d.isoformat(): ["A"] for d in ds}


def test_the_anchor_days_are_the_weekdays_they_claim():
    """Guards the rest of this file against a mis-typed calendar date."""
    assert [d.strftime("%a") for d in (THU, FRI, SAT, SUN, MON, TUE)] == \
        ["Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]


def test_streak_counts_run_ending_today():
    assert stats.current_streak(days(THU, FRI, MON, TUE), "A", TUE) == 4


def test_streak_survives_a_not_yet_ticked_today():
    """Must not read 0 every morning before you have ticked."""
    assert stats.current_streak(days(THU, FRI, MON), "A", TUE) == 3


def test_friday_to_monday_is_unbroken():
    """The headline rule: the weekend does not break a run."""
    assert stats.current_streak(days(FRI, MON), "A", MON) == 2


def test_friday_alone_survives_the_weekend():
    assert stats.current_streak(days(FRI), "A", SAT) == 1
    assert stats.current_streak(days(FRI), "A", SUN) == 1
    # Monday, not yet ticked — Friday's run is still alive.
    assert stats.current_streak(days(FRI), "A", MON) == 1


def test_weekend_completion_does_not_extend_a_streak():
    """Weekends count neither for nor against."""
    assert stats.current_streak(days(FRI, SAT, SUN), "A", SUN) == 1
    assert stats.current_streak(days(FRI, SAT, SUN, MON), "A", MON) == 2


def test_weekend_completion_alone_is_not_a_streak():
    assert stats.current_streak(days(SAT, SUN), "A", SUN) == 0


def test_a_missed_weekday_still_breaks_the_run():
    """The grace covers today only; by Monday, Friday's chance has gone."""
    assert stats.current_streak(days(THU), "A", MON) == 0


def test_streak_of_one_for_today_only():
    assert stats.current_streak(days(MON), "A", MON) == 1


def test_streak_zero_for_empty_log_or_unknown_habit():
    assert stats.current_streak({}, "A", MON) == 0
    assert stats.current_streak(days(FRI, MON), "B", MON) == 0


def test_streak_ignores_other_habits():
    log = days(THU, FRI, MON)
    log[MON.isoformat()].append("B")
    assert stats.current_streak(log, "B", MON) == 1


# --- longest streak --------------------------------------------------------

def test_longest_streak_spans_weekends():
    assert stats.longest_streak(days(FRI, MON, TUE), "A") == 3


def test_longest_streak_ignores_weekend_entries():
    assert stats.longest_streak(days(FRI, SAT), "A") == 1


def test_longest_streak_picks_the_best_run():
    log = days(THU, FRI, MON, TUE, date(2026, 9, 25))
    assert stats.longest_streak(log, "A") == 4


def test_longest_streak_over_two_full_weeks():
    every = [date(2026, 9, 7) + timedelta(days=i) for i in range(12)]
    assert stats.longest_streak(days(*every), "A") == 10


def test_longest_streak_empty():
    assert stats.longest_streak({}, "A") == 0


# --- rates (weekday-only) --------------------------------------------------

def test_completion_rate_counts_weekdays_only():
    """Including weekends would cap a perfect week at ~71%."""
    every = [MON - timedelta(days=i) for i in range(30)]
    assert stats.completion_rate(days(*every), "A", MON, 10) == 1.0


def test_completion_rate_partial():
    assert stats.completion_rate(days(MON, FRI), "A", MON, 4) == 0.5


def test_completion_rate_zero_days_is_not_a_division_error():
    assert stats.completion_rate({}, "A", MON, 0) == 0.0


# --- month grid ------------------------------------------------------------

def test_month_grid_returns_one_block_per_month():
    blocks = stats.month_grid({}, "A", date(2026, 9, 13), months=6)
    assert [b["label"] for b in blocks] == ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]


def test_month_grid_pads_so_columns_are_weekdays():
    """2026-07-01 is a Wednesday, so the block needs two leading pad cells."""
    block = stats.month_grid({}, "A", date(2026, 7, 20), months=1)[0]
    pads = [c for c in block["cells"] if c["state"] == "pad"]
    assert len(pads) == 2
    assert block["cells"][2]["day"] == date(2026, 7, 1)


def test_month_grid_covers_every_day_of_the_month():
    block = stats.month_grid({}, "A", date(2026, 8, 31), months=1)[0]
    assert len([c for c in block["cells"] if c["day"]]) == 31


def test_month_grid_marks_future_days_separately_from_misses():
    block = stats.month_grid({}, "A", date(2026, 9, 13), months=1)[0]
    by_day = {c["day"].day: c["state"] for c in block["cells"] if c["day"]}
    assert by_day[12] == "miss"      # passed, not done
    assert by_day[14] == "future"    # not yet


def test_month_grid_flags_weekends():
    block = stats.month_grid({}, "A", date(2026, 9, 30), months=1)[0]
    weekend_days = {c["day"].day for c in block["cells"] if c["day"] and c["weekend"]}
    assert 12 in weekend_days and 13 in weekend_days   # Sat + Sun
    assert 14 not in weekend_days                      # Mon


def test_month_grid_marks_completions():
    block = stats.month_grid(days(MON), "A", date(2026, 9, 30), months=1)[0]
    by_day = {c["day"].day: c["state"] for c in block["cells"] if c["day"]}
    assert by_day[14] == "done"


# --- store -----------------------------------------------------------------

@pytest.fixture
def private(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRIVATE_DIR", tmp_path)
    monkeypatch.setattr(config, "HABITS_FILE", tmp_path / "habits.json")
    monkeypatch.setattr(config, "LOG_FILE", tmp_path / "habit_log.json")
    monkeypatch.setattr(config, "TOKEN_FILE", tmp_path / "habit_token.txt")
    return tmp_path


def test_log_round_trip(private):
    store.save_log({"2026-09-13": ["A", "B"]})
    assert store.load_log() == {"2026-09-13": ["A", "B"]}


def test_atomic_write_leaves_no_tmp(private):
    store.save_log({"2026-09-13": ["A"]})
    assert not list(private.glob("*.tmp"))


def test_missing_files_degrade_to_empty(private):
    assert store.load_habits() == []
    assert store.load_log() == {}


def test_corrupt_files_degrade_instead_of_raising(private):
    config.HABITS_FILE.write_text("{ not json")
    config.LOG_FILE.write_text("[[[")
    assert store.load_habits() == []
    assert store.load_log() == {}


def test_habits_file_ignores_non_strings_and_blanks(private):
    config.HABITS_FILE.write_text('["Alpha", "", 7, "  Beta  ", null]')
    assert store.load_habits() == ["Alpha", "Beta"]


def test_set_done_adds_and_removes(private):
    log = {}
    store.set_done(log, TODAY, "A", True)
    assert store.done_on(log, TODAY) == {"A"}
    store.set_done(log, TODAY, "A", False)
    # An emptied day is dropped rather than left as an empty list.
    assert TODAY.isoformat() not in log


def test_token_is_stable_across_calls(private):
    first = store.load_token()
    assert first and store.load_token() == first


def test_token_file_is_owner_only(private):
    store.load_token()
    assert (config.TOKEN_FILE.stat().st_mode & 0o077) == 0


# --- service ---------------------------------------------------------------

def test_toggle_bumps_version_only_on_real_change(private, monkeypatch):
    from apps.dashboard.habits import service

    config.HABITS_FILE.write_text('["Alpha", "Beta"]')
    service._snapshot = service.Snapshot()
    service.reload_from_disk()

    v0 = service.get_snapshot().version
    service.toggle("Alpha")
    v1 = service.get_snapshot().version
    assert v1 > v0
    assert "Alpha" in service.get_snapshot().done

    # Toggling an unknown habit must change nothing.
    service.toggle("Nope")
    assert service.get_snapshot().version == v1

    service.toggle("Alpha")
    assert "Alpha" not in service.get_snapshot().done


def test_snapshot_reports_not_configured_when_no_habits(private):
    from apps.dashboard.habits import service
    service._snapshot = service.Snapshot()
    service.reload_from_disk()
    assert not service.get_snapshot().configured
