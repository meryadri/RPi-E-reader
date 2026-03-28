# RPi E-Reader

A Raspberry Pi e-ink e-reader, developed and tested entirely on your laptop before touching any hardware.

## How it works

The app is split into three layers:

1. **HAL** (`hal/`) — thin interface for display and input. On your laptop it uses a pygame window. On the Pi it will use the e-ink HAT driver. Everything above this layer is identical on both platforms.
2. **Core engine** (`core/`) — EPUB parsing, text pagination, page rendering with Pillow, and the screen state machine.
3. **Screens** (`screens/`) — each screen (library, reader, upload info) is a self-contained class that renders to a Pillow image and handles button events.

Data flow: button press → state machine → active screen → Pillow image → display abstraction → pygame window (laptop) or e-ink HAT (Pi).

## Project structure

```
├── main.py               # Laptop simulator entry point
├── upload_server.py      # Flask server for wireless EPUB uploads
├── hal/
│   ├── display_base.py   # Abstract display interface
│   ├── input_base.py     # Button enum and ButtonEvent
│   └── simulator.py      # pygame backend (laptop only)
├── core/
│   ├── state_machine.py  # Screen base class and state machine
│   ├── epub_parser.py    # EPUB → text paragraphs
│   ├── paginator.py      # Paragraphs → pages (word wrap + line fit)
│   └── renderer.py       # Page → Pillow image
├── screens/
│   ├── library.py        # Book list with cursor navigation
│   ├── reader.py         # Page-by-page reader with progress saving
│   └── upload_info.py    # Displays the upload server URL
├── data/
│   └── database.py       # SQLite: books, reading progress, settings
└── uploads/              # Uploaded EPUB files are stored here
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running on your laptop

**Simulator** — opens an 800×480 pygame window:

```bash
python main.py
```

**Upload server** — open `http://localhost:5000` in your browser to upload EPUB files:

```bash
python upload_server.py
```

Both can run at the same time in separate terminals. Books uploaded via the web interface appear immediately in the simulator's library.

### Keyboard controls

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate list / scroll |
| `←` / `→` | Previous / next page |
| `Enter` | Select / open |
| `Esc` | Back |
| `M` | Menu |

## Display

Target resolution: **800 × 480** pixels (matches common 7.5" e-ink HATs for the Pi).

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
