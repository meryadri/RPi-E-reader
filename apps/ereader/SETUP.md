# E-reader setup

Portrait EPUB reader, driven by physical buttons.

**Do [SETUP.md](../../SETUP.md) first** — display, SPI, time zone and the Python
environment are shared with the dashboard. This page covers only what the
e-reader needs on top.

---

## 1. Wire the buttons

Each button has two legs: one to a GPIO pin, the other to any **GND** pin.
Internal pull-ups are enabled in software, so no resistors are needed.

| Button | BCM pin | Physical pin | |
|---|---|---|---|
| UP | 5 | 29 | |
| DOWN | 27 | 13 | |
| LEFT | 22 | 15 | optional |
| RIGHT | 23 | 16 | optional |
| SELECT | 6 | 31 | |
| BACK | 13 | 33 | |
| MENU | 26 | 37 | |

UP, SELECT and BACK deliberately avoid GPIO 17, 24 and 25, which the e-ink panel
uses for RST, BUSY and DC.

Omitting LEFT and RIGHT gives a working 5-button layout; page turns then fall to
UP/DOWN. The map lives in `GPIO_MAP` in `display/hal/rpi.py` if you want to
change pins.

UP and DOWN take the most presses — larger buttons or a rocker help.

## 2. GPIO library

Unlike the dashboard, the e-reader needs a working GPIO library:

```bash
source venv/bin/activate
pip install RPi.GPIO
```

On newer Pi models the GPIO controller changed, and `RPi.GPIO` may not work.
The Waveshare installer can also leave behind a `Jetson.GPIO` shim that
masquerades as `RPi.GPIO` and fails with *"Could not determine Jetson model"*.
Check what you actually have:

```bash
python -c "import RPi.GPIO as G; print(G.__file__)"
```

If that path is under `Jetson/`, uninstall it (`pip uninstall Jetson.GPIO`) and
install a GPIO library that supports your board.

## 3. Run

```bash
source venv/bin/activate
python main.py --app ereader --backend rpi
```

| Backend | Use |
|---|---|
| `rpi` | e-ink panel, GPIO buttons |
| `rpi_ssh` | e-ink panel, keyboard over SSH (handy before buttons are wired) |
| `sim` | laptop pygame window |

## 4. Add books

Press `M` for Settings, toggle **Upload Server ON**, then open the URL shown on
screen. Drag EPUBs into the page.

The server is off by default and only listens on your local network.

---

## Controls

| Key / Button | Action |
|---|---|
| UP / DOWN | Navigate list, scroll |
| LEFT / RIGHT | Previous / next page |
| SELECT | Open |
| BACK | Back |
| MENU | Settings |

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Could not determine Jetson model` | The `Jetson.GPIO` shim — see step 2 |
| Buttons do nothing | Wrong pins, or the second leg not on GND |
| One button fires twice | Bounce; raise `DEBOUNCE_MS` in `display/hal/rpi.py` |
| Display works, buttons don't | Try `--backend rpi_ssh` to confirm the app itself is fine |
