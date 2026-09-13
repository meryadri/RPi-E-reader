# Privacy Policy

**RPi E-ink Dashboard** — last updated 13 September 2026

This is a personal, self-hosted hobby project. It runs entirely on hardware owned
by the person who installed it (a Raspberry Pi with an e-ink display) and is not
offered as a service to anyone else.

## What data is accessed

If you connect a Google account, the app requests a single scope:

```
https://www.googleapis.com/auth/calendar.readonly
```

This is **read-only**. The app cannot create, modify, or delete anything in your
Google Calendar.

Using that scope, it reads:

- the list of calendars your account is subscribed to, and
- events on those calendars for the current day.

Only all-day events for the current day are displayed.

## How data is used

Calendar event titles are drawn on a locally attached e-ink display, so the owner
of the device can see their own schedule. That is the only use.

## How data is stored

- Today's events are cached in a plain file on the device
  (`data/calendar_cache.json`) so the display still works when the network is
  down. This cache is discarded and refetched when the date changes.
- OAuth credentials are stored on the device
  (`integrations/google_calendar/secrets/token.json`, file mode `0600`).

Both files stay on the device. There is no server, no database, and no account
system.

## How data is shared

Calendar data is **never transmitted anywhere**. The only network connection the
integration makes is directly to Google's own Calendar API to fetch your data.
Nothing is sent to the developer, to any analytics service, or to any third
party. No data is sold or shared under any circumstances.

## Retention and deletion

To delete all stored data, delete the two files listed above, or run
`python dev_reset.py` and remove `token.json`.

You can revoke the app's access to your Google account at any time at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions).
Revoking takes effect immediately and requires no action on the device.

## Limited Use disclosure

This app's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

## Contact

Via issues on the project repository:
<https://github.com/meryadri/RPi-E-reader>

## Source

The entire application is open source and auditable at the repository above. The
Google Calendar integration lives in `integrations/google_calendar/`.
