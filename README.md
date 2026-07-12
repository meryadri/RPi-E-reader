# RPi E-ink Platform

A Raspberry Pi e-ink platform (Waveshare 7.5" 800×480 HAT), developed and tested
entirely on your laptop before touching hardware. A small reusable **display core**
hosts multiple **apps**:

- **E-reader** — portrait, button-driven EPUB reader with a wireless upload site.
- **Dashboard** — landscape, no buttons; shows the time, weather, calendar events,
  and a running training plan. (Data is currently a hardcoded stub — see below.)

## How it works

The code is split into a reusable core and per-app packages:

1. **Display core** (`display/`) — everything app-agnostic:
   - `hal/` — thin display + input interface. On your laptop it uses a pygame
     window (`simulator.py`); on the Pi it uses the e-ink HAT (`rpi.py` for GPIO
     buttons, `rpi_ssh.py` for keyboard-over-SSH). Everything above the HAL is
     identical on both platforms.
   - `runtime.py` — the `Screen` base class, `StateMachine`, the `App` descriptor,
     and the shared main loop (`run()`). Orientation is a per-app `(width, height)`:
     `PORTRAIT = (480, 800)`, `LANDSCAPE = (800, 480)`.
   - `fonts.py` — central font loader (CommitMono variants + system fallback).
2. **Apps** (`apps/`) — each app declares an `APP` object (orientation, root screen,
   whether it uses input) in its `app.py`, and provides its own screens.

Data flow: input event → state machine → active screen → Pillow image → display
abstraction → pygame window (laptop) or e-ink HAT (Pi). Orientation is chosen by the
app, so the same core renders portrait or landscape without changes to screen code.

## Project structure

```
├── main.py                       # Launcher:  --app ereader|dashboard  --backend sim|rpi|rpi_ssh
├── display/                      # Reusable, app-agnostic display core
│   ├── runtime.py                # Screen, StateMachine, App, run(), PORTRAIT/LANDSCAPE
│   ├── fonts.py                  # Central font loader (CommitMono + system)
│   └── hal/
│       ├── display_base.py       # Abstract display (per-instance width/height)
│       ├── input_base.py         # Button enum and ButtonEvent
│       ├── simulator.py          # pygame backend (laptop)
│       ├── rpi.py                # Waveshare e-ink + GPIO buttons (Pi)
│       └── rpi_ssh.py            # Waveshare e-ink + keyboard over SSH (Pi)
├── apps/
│   ├── ereader/                  # Portrait EPUB reader
│   │   ├── app.py                # APP = App(... PORTRAIT ...)
│   │   ├── epub_parser.py        # EPUB → text, year, cover image
│   │   ├── paginator.py          # Paragraphs → pages (word wrap + line fit)
│   │   ├── renderer.py           # Page → Pillow image with progress bar
│   │   ├── page_cache.py         # In-memory paginated-page cache
│   │   ├── metrics_cache.py      # Persistent word-width metrics cache
│   │   ├── server.py             # Flask upload site + start/stop lifecycle
│   │   ├── database.py           # SQLite: books, progress, settings
│   │   └── screens/              # library, reader, settings, upload_info
│   └── dashboard/                # Landscape info dashboard (no buttons)
│       ├── app.py                # APP = App(... LANDSCAPE, uses_input=False ...)
│       ├── data.py               # HARDCODED data stub — swap for real APIs later
│       └── screens/dashboard.py  # Clock, weather, calendar, training layout
├── data/                         # ereader.db, covers/, metrics_cache.pkl (auto-created)
├── assets/fonts/                 # CommitMono font files
├── default_books/                # Seed EPUBs added on first run
└── uploads/                      # Uploaded EPUB files
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running on your laptop

The launcher picks the app (which sets orientation) and the display backend
(`sim` by default):

```bash
python main.py --app ereader      # portrait e-reader
python main.py --app dashboard     # landscape dashboard
```

The simulator window is sized to match the physical footprint of the 7.5" panel,
so a portrait app opens a tall window and a landscape app a wide one.

### E-reader
Button-driven. To upload books, press `M` to open Settings, toggle
**Upload Server ON**, then open the URL shown on screen in your browser.

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate list / scroll |
| `←` / `→` | Previous / next page |
| `Enter` | Select / open |
| `Esc` | Back |
| `M` | Menu |

### Dashboard
No input — it just displays. The clock refreshes once a minute. All content comes
from `apps/dashboard/data.py`, which currently returns **hardcoded** values. That
module is the single seam to replace later with real sources (a weather API, Google
Calendar, a training-plan feed or upload site); the screen layout won't need to change.

## Running on the Raspberry Pi

The e-ink backends already exist — select one with `--backend`:

```bash
python main.py --app ereader  --backend rpi_ssh   # e-ink output, control over SSH keyboard
python main.py --app ereader  --backend rpi        # e-ink output, GPIO buttons
python main.py --app dashboard --backend rpi        # dashboard on e-ink (landscape is native)
```

The Waveshare Python library is not on PyPI — install it from their repo (see the
header of `display/hal/rpi.py` for the exact commands and the GPIO pin map). Landscape
is the panel's native orientation; the portrait e-reader is rendered 480×800 and the
HAL handles the rest.

## Dev reset

Wipes all uploaded books, cover images, and the database (schema is re-created
automatically). Also clears the word-width metrics cache.

```bash
python dev_reset.py
```

## Tests

```bash
python -m pytest tests/ -v -s
```

The `-s` flag is required — timing and memory numbers are printed to stdout and would
be hidden without it.

To run only the pagination timing suite:

```bash
python -m pytest tests/test_pagination_timing.py -v -s
```

The timing tests use `tests/leo-tolstoy_war-and-peace.epub` (committed to the repo).
They cover:

| Test | What it measures |
|------|-----------------|
| `test_parse_epub_time` | EPUB parsing time alone |
| `test_default_settings` | Paginate at default font/size |
| `test_font_sizes` | Speed across the 8–32 px range |
| `test_commit_mono_vs_system` | CommitMono vs System Sans paginate time |
| `test_word_cache_effect` | Confirms consistent per-call speed |
| `test_word_cache_memory` | Unique word count + cache memory in KB |
| `test_paginate_peak_memory` | Peak memory allocated during paginate() via tracemalloc |
| `test_page_cache_hit` | Cold parse+paginate vs warm cache-hit speedup |

## Adding a new app

1. Create `apps/<name>/app.py` exporting `APP = App(name=..., size=PORTRAIT|LANDSCAPE,
   build_root=..., uses_input=..., setup=...)`.
2. Add screens under `apps/<name>/screens/` subclassing `display.runtime.Screen`
   (implement `render()` and `handle()`; override `poll()` for timer-driven redraws).
3. Add the name to the launcher's `--app` choices in `main.py`.

## Display

Physical panel: **800 × 480** pixels (7.5" Waveshare e-ink HAT). Apps render at their
own logical orientation — the e-reader at 480×800 portrait, the dashboard at 800×480
landscape.

## Stack

- [ebooklib](https://github.com/aerkalov/ebooklib) — EPUB parsing (e-reader)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML text extraction (e-reader)
- [Pillow](https://python-pillow.org/) — image rendering
- [Flask](https://flask.palletsprojects.com/) — upload web server (e-reader)
- [pygame](https://www.pygame.org/) — laptop simulator display and input
- SQLite3 — built-in, no install needed
- [Tailwind CSS](https://tailwindcss.com/) — web UI styling via CDN (no install needed)
```
