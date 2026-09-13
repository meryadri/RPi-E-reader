# Google Calendar integration

Fetches **today's all-day events** from your Google calendars and hands them to
the dashboard app. Read-only — the scope used cannot modify anything.

Setup uses a **service account**: a robot Google account that you share your
calendars with. There is no consent screen, no browser step, and no token that
expires. This is the right shape for a headless device.

> **Why not the normal OAuth flow?** It needs a *published* OAuth consent
> screen, and Google will only publish one if you supply a homepage and privacy
> policy on a domain you can verify in Google Search Console. There is no way
> around that with a GitHub URL. The OAuth path is still implemented as a
> fallback (see the bottom of this file) if you ever have a verified domain.

---

## 1. Create the service account

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create
   a project (e.g. `rpi-eink-dashboard`).
2. **APIs & Services → Library → Google Calendar API → Enable.**
3. **IAM & Admin → Service Accounts → Create service account.**
   - Name it anything (`rpi-dashboard`).
   - Skip the optional "grant access" steps — it needs no project roles.
4. Open the new service account → **Keys → Add key → Create new key → JSON.**
   Save the download as:

   ```
   integrations/google_calendar/secrets/service_account.json
   ```

   Everything in `secrets/` is gitignored wholesale, including by a `.gitignore`
   inside that directory, so it cannot be committed by accident.

You never touch the OAuth consent screen. There is nothing to publish.

## 2. Find the robot's email address

```bash
python -m integrations.google_calendar
```

It prints something like:

```
Auth mode: service_account
Service account: rpi-dashboard@rpi-eink-dashboard.iam.gserviceaccount.com
Calendars must be shared with that address.
```

Copy that address.

## 3. Share your calendars with it

For **each** calendar you want on the dashboard, in
[Google Calendar](https://calendar.google.com):

1. Hover the calendar in the left sidebar → **⋮ → Settings and sharing**.
2. **Share with specific people or groups → Add people** → paste the service
   account address.
3. Permission: **See all event details**. (Not "See only free/busy" — that
   returns events with no titles.)
4. On the same settings page, scroll to **Integrate calendar** and copy the
   **Calendar ID**. For your main calendar this is just your Gmail address.

Then tell the app about each one:

```bash
python -m integrations.google_calendar --add-calendar you@gmail.com
python -m integrations.google_calendar --add-calendar abc123...@group.calendar.google.com
```

That checks the calendar is actually readable and appends its id to
`secrets/calendars.json`. It makes no write call to Google — a service account
has no calendar list of its own, and registering one would need a write scope
this integration deliberately never requests.

### What you cannot share

Google-generated calendars have no sharing settings, so a service account cannot
read them:

- **Birthdays** (built from your Contacts)
- **Holidays in …** and other subscribed public calendars

Only calendars you own can be shared. If you specifically want birthdays or
holidays on the dashboard, the options are to recreate them as a normal calendar
you own, or to use the OAuth fallback below with a verified domain.

## 4. Verify

```bash
python -m integrations.google_calendar
```

Prints the calendars it can see and today's all-day events. This works over SSH
and is the fastest way to tell "the API is broken" from "the display is broken".

## 5. Copy to the Pi

```bash
scp integrations/google_calendar/secrets/service_account.json \
    pi@raspberrypi.local:~/RPi-E-reader-/integrations/google_calendar/secrets/
ssh pi@raspberrypi.local \
    chmod 600 ~/RPi-E-reader-/integrations/google_calendar/secrets/service_account.json
```

The key is a **permanent credential** — treat the Pi's filesystem accordingly.
To revoke it, delete the key in the Cloud console (IAM → Service Accounts →
Keys), or remove the sharing from the calendar. Either takes effect immediately
and needs nothing done on the device.

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

| Variable | Default | Meaning |
|---|---|---|
| `GCAL_TZ` | `America/New_York` | IANA zone used to decide what "today" is |
| `GCAL_CALENDAR_IDS` | — | Comma-separated ids, most important first. Merged with `secrets/calendars.json` |
| `GCAL_REFRESH_SECONDS` | `1800` | Ordinary poll interval (30 min) |
| `GCAL_STALE_AFTER` | `2700` | Age at which the panel shows an "as of HH:MM" marker |
| `GCAL_BIRTHDAYS` | `1` | Set `0` to hide birthday events |
| `GCAL_HIDE_DECLINED` | `1` | Set `0` to show events you declined |
| `GCAL_EXCLUDE_IDS` | — | Comma-separated calendar ids to skip |
| `GCAL_EXCLUDE_NAMES` | — | Comma-separated name substrings to skip |
| `GCAL_SECRETS_DIR` | `./secrets` | Move credentials elsewhere (e.g. `~/.config`) |

### How often it fetches

1. **Startup** — immediately, so the panel is right as soon as it boots.
2. **Local midnight** — the one that matters. "Today" changes, so the event list
   must change with it. Detected by re-reading the date every 30 seconds rather
   than sleeping until midnight, which is immune to suspend/resume, NTP step
   corrections, DST, and the Pi's lack of a real-time clock.
3. **Every 30 minutes otherwise** — this only covers same-day edits, which are
   rare for all-day events. Quota is a non-issue (Google allows 1,000,000
   queries/day).

On failure it backs off 30s → 60s → 120s → 300s. **A fetch returning unchanged
events writes nothing to the e-ink panel** — the snapshot's `version` only
increments when the rendered content actually differs.

### What gets filtered out

- `workingLocation` events. Google auto-creates one per weekday on your primary
  calendar, so without this "Office" would be the top row every working day.
- Cancelled events, and events *you* have declined.
- Calendars you only have free/busy access to — their events have no titles.

---

## Troubleshooting

Run `python -m integrations.google_calendar` first — it isolates the API from
the display.

| Symptom | Cause |
|---|---|
| "Calendar not connected" on the panel | No `service_account.json`, or it's unreadable |
| `0 calendar(s) visible` | Calendar not shared with the robot address, or not yet registered with `--add-calendar` |
| Events have no titles | Calendar was shared as "See only free/busy" — change to "See all event details" |
| `--add-calendar` says "Cannot read" | The calendar isn't shared with the robot address yet, or the id is wrong |
| Birthdays/holidays missing | Expected — Google-generated calendars can't be shared (see above) |
| Events show on the wrong day | The Pi's time zone. `timedatectl set-timezone`, or set `GCAL_TZ` |
| An event never appears | Check the `--check` output. It may be a `workingLocation` event or one you declined |

---

## OAuth fallback

If you have a domain verified in Google Search Console, you can use the normal
installed-app flow instead and get access to *all* subscribed calendars,
birthdays and holidays included.

1. Publish an OAuth consent screen (needs homepage + privacy policy on your
   verified domain). **Publish before authorising** — while the app is in
   "Testing" the refresh token expires after 7 days.
2. Create an OAuth client of type **Desktop app**, save it as
   `secrets/credentials.json`.
3. `python -m integrations.google_calendar --auth`
4. Copy the resulting `secrets/token.json` to the Pi.

`auth.py` prefers `service_account.json` when both are present — delete it to use
the OAuth token.

---

## Layout

| File | Role |
|---|---|
| `config.py` | Tunables, paths, env overrides |
| `auth.py` | Service-account and OAuth credential loading |
| `client.py` | API calls only |
| `events.py` | Pure date/filter logic — no network, fully unit-tested |
| `cache.py` | Last-good snapshot at `data/calendar_cache.json` |
| `service.py` | Refresh thread and the immutable snapshot apps read |
| `__main__.py` | `--check` / `--add-calendar` / `--auth` |

`events.py` is deliberately free of network and Google objects: all the
correctness risk here is date arithmetic, so it lives somewhere `pytest` can
reach offline. See `tests/test_calendar_events.py`.
