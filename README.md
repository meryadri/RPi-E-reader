# RPi E-Reader

A Raspberry Pi e-ink e-reader, developed and tested entirely on your laptop before touching any hardware.

## How it works

The app is split into three layers:

1. **HAL** (`hal/`) — thin interface for display and input. On your laptop it uses a pygame window. On the Pi it will use the e-ink HAT driver. Everything above this layer is identical on both platforms.
2. **Core engine** (`core/`) — EPUB parsing, text pagination, page rendering with Pillow, the screen state machine, and the upload server lifecycle manager.
3. **Screens** (`screens/`) — each screen (library, reader, settings) is a self-contained class that renders to a Pillow image and handles button events.

Data flow: button press → state machine → active screen → Pillow image → display abstraction → pygame window (laptop) or e-ink HAT (Pi).

## Project structure

```
├── main.py                   # Laptop simulator entry point
├── upload_server.py          # Flask server (standalone or via settings screen)
├── hal/
│   ├── display_base.py       # Abstract display interface (480×800 portrait)
│   ├── input_base.py         # Button enum and ButtonEvent
│   └── simulator.py          # pygame backend (laptop only)
├── core/
│   ├── fonts.py              # Central font loader (CommitMono variants)
│   ├── state_machine.py      # Screen base class and state machine
│   ├── epub_parser.py        # EPUB → text, year, cover image
│   ├── paginator.py          # Paragraphs → pages (word wrap + line fit)
│   ├── renderer.py           # Page → Pillow image with progress bar
│   └── server_manager.py     # Start/stop Flask in a background thread
├── screens/
│   ├── library.py            # Scrollable book list with cover thumbnails
│   ├── reader.py             # Page-by-page reader with progress saving
│   └── settings.py           # Font size and upload server toggle
├── data/
│   ├── database.py           # SQLite: books, progress, settings
│   └── covers/               # Extracted cover images (auto-created)
├── assets/fonts/             # CommitMono font files
└── uploads/                  # Uploaded EPUB files
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running on your laptop

```bash
python main.py
```

That's it. The simulator opens a portrait pygame window. The upload server is started and stopped from **inside the app** — press `M` to open Settings, then toggle **Upload Server ON**. The screen will show the URL to open in your browser.

### Optional: run the upload server standalone

If you prefer to always have the server running during development (without going through the settings screen), you can still launch it directly:

```bash
python upload_server.py
```

Open `http://localhost:3003` in your browser. This is useful during development but not needed in normal use.

### Keyboard controls

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate list / scroll |
| `←` / `→` | Previous / next page |
| `Enter` | Select / open |
| `Esc` | Back |
| `M` | Menu |

## Display

Target resolution: **480 × 800** pixels portrait (7.5" e-ink HAT, ~124 PPI). The simulator window is sized to match the physical footprint of the screen on your desk.

## Porting to Raspberry Pi

Only one new file is needed: `hal/eink.py`. Implement the `DisplayBase` interface using your e-ink HAT's Python library, then swap it in at the top of `main.py`. All core logic, screens, and the database layer stay untouched.

```python
# hal/eink.py  (skeleton)
from hal.display_base import DisplayBase
from PIL import Image

class EinkDisplay(DisplayBase):
    def show(self, image: Image.Image) -> None:
        # call your HAT library here
        ...

    def clear(self) -> None:
        # call your HAT library here
        ...
```

## Stack

- [ebooklib](https://github.com/aerkalov/ebooklib) — EPUB parsing
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML text extraction
- [Pillow](https://python-pillow.org/) — image rendering
- [Flask](https://flask.palletsprojects.com/) — upload web server
- [pygame](https://www.pygame.org/) — laptop simulator display and input
- SQLite3 — built-in, no install needed
- [Tailwind CSS](https://tailwindcss.com/) — web UI styling via CDN (no install needed)
