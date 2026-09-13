# Google Calendar integration

Fetches **today's all-day events** across all your subscribed calendars and hands
them to the dashboard app. Read-only — the scope used cannot modify your calendar.

Setup is a one-time job on a machine with a browser (your laptop). The Pi only
ever needs the resulting `token.json`.

---

## 1. Google Cloud console

1. Go to [console.cloud.google.com](https://console.cl oud.google.com) and create a
   project (e.g. `rpi-eink-dashboard`).
2. **APIs & Services → Library → Google Calendar API → Enable.**
3. **OAuth consent screen** → User type **External**. (A personal Gmail account
   cannot use _Internal_ — that requires Google Workspace.) Fill in the app name
   and the two email fields, and add your own Gmail as a **Test user**.
4. **Publish the app.** Under _Audience_, click **Publish app** so the status
   changes from "Testing" to "In production".

   > **Do this before step 6.** While the app is in Testing, a refresh token for
   > a sensitive scope — which `calendar.readonly` is — **expires after 7 days**,
   > and the dashboard would silently stop updating every week. If you authorise
   > while still in Testing, the token you copy to the Pi is already on that
   > 7-day clock and you will have to redo it.
   >
   > Publishing needs no Google verification review for personal use. You will
   > see a "Google hasn't verified this app" screen once during consent —
   > _Advanced → Go to … (unsafe)_. The 100-user cap on unverified apps is
   > irrelevant for a single user.

5. **Credentials → Create credentials → OAuth client ID → Application type:
   Desktop app.** Download the JSON and save it as:

   ```
   integrations/google_calendar/secrets/credentials.json
   ```

   (Google names the download `client_secret_…apps.googleusercontent.com.json`;
   rename it. Everything in `secrets/` is gitignored wholesale.)

## 2. Authorise, on the laptop

```bash
pip install -r requirements.txt
python -m integrations.google_calendar
```

A browser opens, you approve, and `secrets/token.json` is written with mode
`0600`. The out-of-band console flow was removed by Google in 2022, so this step
genuinely needs a browser — hence doing it here and copying the result.

Verify it actually works before touching the Pi:

```bash
python -m integrations.google_calendar --check
```

That prints your calendars and today's all-day events as plain text. It is the
fastest way to tell "the API is broken" apart from "the display is broken", and
it works over SSH.

## 3. Copy to the Pi

Copy **`token.json` only**. It already embeds the client id, client secret and
refresh token, so the Pi does not need `credentials.json` — leave the client
secret on your laptop.

```bash
scp integrations/google_calendar/secrets/token.json \
    pi@raspberrypi.local:~/RPi-E-reader-/integrations/google_calendar/secrets/
ssh pi@raspberrypi.local \
    chmod 600 ~/RPi-E-reader-/integrations/google_calendar/secrets/token.json
```

The `expiry` in the copied file will be stale; it refreshes automatically on
first use.

**Also set the Pi's time zone.** A freshly imaged Raspberry Pi OS runs on UTC,
which would roll the dashboard over to "tomorrow" at 8pm Eastern — and it works
perfectly on your laptop, so the simulator will never show you the bug.

```bash
sudo timedatectl set-timezone America/New_York
timedatectl          # confirm NTP is synchronised
```

---

## Configuration

All via environment variable; defaults are in `config.py`.

| Variable               | Default            | Meaning                                              |
| ---------------------- | ------------------ | ---------------------------------------------------- |
| `GCAL_TZ`              | `America/New_York` | IANA zone used to decide what "today" is             |
| `GCAL_REFRESH_SECONDS` | `1800`             | Ordinary poll interval (30 min)                      |
| `GCAL_STALE_AFTER`     | `2700`             | Age at which the panel shows an "as of HH:MM" marker |
| `GCAL_BIRTHDAYS`       | `1`                | Set `0` to hide birthdays                            |
| `GCAL_HIDE_DECLINED`   | `1`                | Set `0` to show events you declined                  |
| `GCAL_EXCLUDE_IDS`     | —                  | Comma-separated calendar ids to skip                 |
| `GCAL_EXCLUDE_NAMES`   | —                  | Comma-separated name substrings to skip              |
| `GCAL_SECRETS_DIR`     | `./secrets`        | Move credentials elsewhere (e.g. `~/.config`)        |

### How often it fetches

Three things trigger a fetch:

1. **Startup** — immediately, so the panel is right as soon as it boots.
2. **Local midnight** — the one that matters. "Today" changes, so the event list
   must change with it. Detected by re-reading the date every 30 seconds rather
   than sleeping until midnight, which is immune to suspend/resume, NTP step
   corrections, DST, and the Pi's lack of a real-time clock.
3. **Every 30 minutes otherwise** — this only covers same-day edits, which are
   rare for all-day events. Quota is a non-issue (Google allows 1,000,000
   queries/day; ~10 calendars at this cadence is a few hundred).

On failure it backs off 30s → 60s → 120s → 300s so a Wi-Fi blip doesn't leave
the panel stale for a full interval. On an auth failure it backs off to hourly,
since a revoked token will not fix itself.

**A fetch that returns unchanged events writes nothing to the e-ink panel.** The
snapshot's `version` only increments when the rendered content actually differs.

### What gets filtered out

- `workingLocation` events. Google auto-creates one per weekday on your primary
  calendar, so without this "Office" would be the top row every working day.
- Cancelled events, and events _you_ have declined.
- Calendars you only have `freeBusyReader` access to — their events come back
  with no title at all.

Birthdays and holidays are **kept** (they're the point of an all-day dashboard).
If a holiday calendar floods the panel, add it to `GCAL_EXCLUDE_NAMES`.

---

## Troubleshooting

Run `python -m integrations.google_calendar --check` first — it isolates the
API from the display.

| Symptom                                 | Cause                                                                                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Panel shows "Calendar not connected"    | No `token.json`, or it was revoked. Re-run the bootstrap.                                                                       |
| Worked for exactly 7 days, then stopped | The OAuth app was still in "Testing" when you authorised. Publish it (step 4), then re-run the bootstrap.                       |
| `invalid_grant`                         | Access revoked, 6+ months unused, or a password change. Re-run the bootstrap.                                                   |
| Stops working ~1 hour after setup       | No refresh token was issued. Revoke at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) and re-run. |
| Events show on the wrong day            | The Pi's time zone. `timedatectl set-timezone`, or set `GCAL_TZ`.                                                               |
| An event on your calendar never appears | Check `--check` output. If it's missing there, it may be a `workingLocation` event or one you've declined.                      |
| No calendars returned                   | The Calendar API isn't enabled on the project (step 2).                                                                         |

### Revoking access

[myaccount.google.com/permissions](https://myaccount.google.com/permissions) →
find the app → _Remove access_. The token on the Pi stops working immediately;
nothing needs to be done on the device.

---

## Layout

| File         | Role                                                   |
| ------------ | ------------------------------------------------------ |
| `config.py`  | Tunables, paths, env overrides                         |
| `auth.py`    | OAuth bootstrap, credential loading, `--check`         |
| `client.py`  | API calls only                                         |
| `events.py`  | Pure date/filter logic — no network, fully unit-tested |
| `cache.py`   | Last-good snapshot at `data/calendar_cache.json`       |
| `service.py` | Refresh thread and the immutable snapshot apps read    |

`events.py` is deliberately free of network and Google objects: all the
correctness risk in this feature is date arithmetic, so it's kept somewhere that
`pytest` can reach offline. See `tests/test_calendar_events.py`.
