"""
Raspberry Pi hardware backend.

Display  : Waveshare 7.5" e-ink HAT V2 (800×480, black/white).
Input    : 5–7 tactile buttons wired to GPIO with internal pull-ups.

GPIO pin map (BCM numbering)
-----------------------------
   5 → UP         (moved from 17 — conflicts with e-ink RST)
  27 → DOWN
  22 → LEFT       (omit if using 5-button layout)
  23 → RIGHT      (omit if using 5-button layout)
   6 → SELECT     (moved from 24 — conflicts with e-ink BUSY)
  13 → BACK       (moved from 25 — conflicts with e-ink DC)
  26 → MENU

Wiring
------
One leg of each button goes to the GPIO pin listed above.
The other leg goes to any GND pin on the Pi header.
Internal pull-ups are enabled in software — no external resistors needed.

E-ink library installation
---------------------------
The Waveshare Python library is not on PyPI. Install it from their repo:

  git clone https://github.com/waveshare/e-Paper
  pip install ./e-Paper/RaspberryPi_JetsonNano/python/

Then import it as:  from waveshare_epd import epd7in5_V2

If you are using a different Waveshare model, replace the import and adapt
the init/display calls — the Pillow interface is identical across models.

Swapping in this backend
------------------------
In main_rpi.py, replace SimulatorDisplay with RpiDisplay:

  from hal.rpi import RpiDisplay
  display = RpiDisplay()
"""
from __future__ import annotations
import queue
import signal
import threading
import time
from PIL import Image
from hal.display_base import DisplayBase
from hal.input_base import Button, ButtonEvent

# ---------------------------------------------------------------------------
# GPIO pin → Button mapping  (BCM numbering)
# Remove LEFT / RIGHT entries if using a 5-button layout.
# ---------------------------------------------------------------------------
GPIO_MAP: dict[int, Button] = {
    5:  Button.UP,
    27: Button.DOWN,
    22: Button.LEFT,
    23: Button.RIGHT,
    6:  Button.SELECT,
    13: Button.BACK,
    26: Button.MENU,
}

DEBOUNCE_MS = 20   # milliseconds — increase if you get spurious presses


class RpiDisplay(DisplayBase):
    """
    Hardware backend for Raspberry Pi + Waveshare 7.5" e-ink HAT V2.

    Mirrors the SimulatorDisplay interface so main_rpi.py is a near-copy
    of main.py with only the display constructor swapped.
    """

    # Do a full refresh every N fast refreshes to clear ghosting
    FULL_REFRESH_INTERVAL = 100

    def __init__(self) -> None:
        self._event_queue: queue.Queue[ButtonEvent] = queue.Queue()
        self._running = True
        self._fast_count = 0

        self._epd = self._init_display()
        self._init_gpio()

        # Graceful shutdown on Ctrl-C
        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    # ------------------------------------------------------------------
    # DisplayBase interface
    # ------------------------------------------------------------------

    def show(self, image: Image.Image) -> None:
        """
        Push a Pillow image to the e-ink panel.

        Uses the refresh hint set by the state machine:
        - "partial" → flicker-free partial refresh (page turns)
        - "full"    → full refresh with flicker (screen switches)

        A full refresh is also forced every FULL_REFRESH_INTERVAL
        partial refreshes to clear accumulated ghosting.
        """
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT), Image.LANCZOS)
        bw = image.convert("1")
        buf = self._epd.getbuffer(bw)

        if self._refresh_hint == "partial":
            self._fast_count += 1
            if self._fast_count >= self.FULL_REFRESH_INTERVAL:
                self._epd.init()
                self._epd.display(buf)
                self._fast_count = 0
            else:
                self._epd.init_part()
                self._epd.display_Partial(buf, 0, 0, 800, 480)
        else:
            self._epd.init()
            self._epd.display(buf)
            self._fast_count = 0

    def clear(self) -> None:
        self._epd.Clear()

    # ------------------------------------------------------------------
    # Input  (same API as SimulatorDisplay)
    # ------------------------------------------------------------------

    def poll_event(self) -> ButtonEvent | None:
        """Return the next queued button event, or None if the queue is empty."""
        try:
            return self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internal — display
    # ------------------------------------------------------------------

    def _init_display(self):
        try:
            from waveshare_epd import epd7in5_V2
            epd = epd7in5_V2.EPD()
            epd.init()
            epd.Clear()
            return epd
        except ImportError as exc:
            raise ImportError(
                "Waveshare e-Paper library not found.\n"
                "Install it with:\n"
                "  git clone https://github.com/waveshare/e-Paper\n"
                "  pip install ./e-Paper/RaspberryPi_JetsonNano/python/"
            ) from exc

    # ------------------------------------------------------------------
    # Internal — GPIO
    # ------------------------------------------------------------------

    def _init_gpio(self) -> None:
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise ImportError(
                "RPi.GPIO not found.  Install it with:  pip install RPi.GPIO"
            ) from exc

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        for pin in GPIO_MAP:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # Falling edge = button pressed (pin pulled low through GND)
            GPIO.add_event_detect(
                pin,
                GPIO.BOTH,
                callback=self._gpio_callback,
                bouncetime=DEBOUNCE_MS,
            )

    def _gpio_callback(self, pin: int) -> None:
        btn = GPIO_MAP.get(pin)
        if btn is None:
            return
        # LOW  = pressed (pin pulled to GND through the button)
        # HIGH = released (pin held HIGH by internal pull-up)
        pressed = self._GPIO.input(pin) == self._GPIO.LOW
        self._event_queue.put(ButtonEvent(button=btn, pressed=pressed))

    # ------------------------------------------------------------------
    # Internal — shutdown
    # ------------------------------------------------------------------

    def _shutdown(self, *_) -> None:
        self._running = False
        try:
            self._epd.sleep()       # low-power mode — important for panel longevity
        except Exception:
            pass
        try:
            self._GPIO.cleanup()
        except Exception:
            pass
