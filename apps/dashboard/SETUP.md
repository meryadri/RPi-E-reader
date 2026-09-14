# Dashboard setup

Landscape wall display: clock, weather, today's all-day calendar events and a
daily habit checklist. **No buttons** — it never touches GPIO.

**Do [SETUP.md](../../SETUP.md) first** — display, SPI, time zone and the Python
environment are shared with the e-reader. This page covers only the dashboard.

---

## 1. Copy your private files

None of these are in git, so a fresh clone will not have them. Run on the
machine where you set them up:

```bash
scp integrations/google_calendar/secrets/service_account.json \
    integrations/google_calendar/secrets/calendars.json \
    <user>@<pi-host>:~/RPi-E-reader-/integrations/google_calendar/secrets/

scp private/habits.json <user>@<pi-host>:~/RPi-E-reader-/private/
```

Then on the Pi:

```bash
chmod 600 ~/RPi-E-reader-/integrations/google_calendar/secrets/service_account.json
```

Without them the dashboard still runs — clock and weather work, and the other
two columns read "Calendar not connected" and "No habits configured". That is
the designed empty state, not a failure.

First-time configuration of each source:

- **Calendar** — [integrations/google_calendar/README.md](../../integrations/google_calendar/README.md)
- **Weather** — [integrations/open_meteo/README.md](../../integrations/open_meteo/README.md) (no setup; just set your location)
- **Habits** — [private/README.md](../../private/README.md)

## 2. Check the data sources

```bash
source venv/bin/activate

python -m integrations.open_meteo        # prints a temperature
python -m integrations.google_calendar   # lists your calendars and today's events
```

Both work over SSH and tell you whether a problem is the API or the display.

## 3. Run

```bash
python main.py --app dashboard --backend rpi
```

The console prints the habit URL — open it on your phone and bookmark it:

```
Habits: http://<pi-ip>:3004/?t=<token>
```

Use `--backend sim` on a laptop to preview without hardware.

## 4. Start on boot

```bash
sudo cp deploy/dashboard.service /etc/systemd/system/
sudoedit /etc/systemd/system/dashboard.service     # set User= and the paths
sudo systemctl enable --now dashboard
systemctl status dashboard --no-pager
```

Set your location in the unit file while you are there:

```ini
Environment=WEATHER_LAT=42.325
Environment=WEATHER_LON=-71.085
```

---

## Day to day

| Task | Command |
|---|---|
| Restart after a change | `sudo systemctl restart dashboard` |
| Logs | `journalctl -u dashboard -n 50 --no-pager` |
| Update | `git pull && sudo systemctl restart dashboard` |
| Habit URL again | `journalctl -u dashboard \| grep Habits \| tail -1` |

`--no-pager` avoids systemd's *"terminal is not fully functional"* prompt over SSH.

### Back up your habit history

It lives only on the SD card and is not in git.

```bash
scp <user>@<pi-host>:~/RPi-E-reader-/private/habit_log.json ~/backups/
```

Or tap **Download backup** on the History page.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Calendar not connected" | `service_account.json` missing or unreadable |
| Calendar connects, shows nothing | `calendars.json` didn't copy |
| "No habits configured" | `private/habits.json` didn't copy |
| "Weather unavailable" | No network; it retries and keeps the last reading |
| Habit page won't load | Phone on a different network (guest Wi-Fi is a common cause) |
| Everything a day out | Time zone — see the shared setup guide |
| `Could not determine Jetson model` | Should not happen; the dashboard takes no GPIO. Check you are on current code |
