# private/

Everything in this directory is **gitignored wholesale** — the `.gitignore` here
contains `*`, so any file you drop in is invisible to git regardless of its name.
Only this README and that `.gitignore` are ever committed.

This is where the habit checklist keeps its data, so the habit names themselves
never reach the public repository.

## Setup

Create `habits.json` with your list, in display order:

```json
["Alpha", "Beta", "Gamma", "Delta"]
```

> Those are placeholders. Put your real habits in the file — **never** in this
> README, which *is* committed.

Then start the dashboard. The console prints the URL:

```
Habits: http://<pi-ip>:3004/?t=<token>
```

Open that on your phone and tap a row to toggle it. The e-ink panel repaints
within about a second, because the web server runs in the same process as the
display loop.

The **History** page shows each habit's record as real calendar months —
columns are weekdays, Monday to Sunday — plus current and longest streaks and
7/30/90-day rates.

## Files

| File | Contents |
|---|---|
| `habits.json` | Your habit list (you create this) |
| `habit_log.json` | Completion history, one entry per day |
| `habit_token.txt` | URL token, generated automatically on first run |

`habit_log.json` looks like:

```json
{
 "2026-09-12": ["Alpha", "Gamma"],
 "2026-09-13": ["Alpha", "Beta", "Delta"]
}
```

Plain, sorted and hand-editable — if you forget to tick something, just add it.
About 22 KB per year.

## Weekends don't count

Streaks are counted over **weekdays only**. A missed Saturday never breaks a
run, and a completed Saturday never extends one — do Training on Friday and
again on Monday and the streak is intact, at two.

Weekend completions are still recorded and shown on the calendar (lighter
squares), they just sit outside the streak. The 7/30/90-day rates are also
weekday-only, since counting weekends in the denominator would cap a perfect
week at about 71%.

The grace period covers today only: if you haven't ticked yet today, your run
still stands. But by Saturday, Friday's chance has passed, so a missed Friday
does break it.

## The day rolls over at 4am

Ticking something at 1am counts toward the day before, not the new one. Without
this a late night would silently split across two dates and break a streak.
Change it with `HABIT_ROLLOVER_HOUR=0` for strict midnight.

## Three things to know

**1. Back it up.** This history exists only on the device's SD card and is not in
git. SD cards fail. The *Download backup* button on the History page gives you
the whole log as a file — grab it occasionally.

**2. The Pi is the source of truth.** If you also run the dashboard on a laptop,
that machine has its own `habit_log.json` and your history will split in two.
Copy the file rather than ticking in both places.

**3. The URL token is not a login.** It keeps the habit names from showing up to
anyone who casually scans the home network, which is the real risk here. Anyone
who *has* the URL can read and change your list, and the server is plain HTTP on
the LAN. It is not reachable from outside the network at all, so you cannot tick
things while away from home.

## Renaming a habit

The log is keyed by habit name, so renaming one orphans its history. To keep the
streak, edit `habit_log.json` and replace the old name everywhere it appears.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `HABITS_DIR` | `./private` | Where these files live |
| `HABITS_PORT` | `3004` | Web server port |
| `HABIT_ROLLOVER_HOUR` | `4` | Hour a new habit-day begins |
| `HABIT_HEATMAP_MONTHS` | `6` | How many calendar months the history page shows |
