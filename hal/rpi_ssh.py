"""
Hybrid backend: Waveshare e-ink display + terminal keyboard input over SSH.

Use this for the first test — plug in the e-ink HAT, SSH into the Pi from
your computer, and control the reader with your computer keyboard while the
output goes to the e-ink screen.

Usage:
    python main_rpi_ssh.py

Key bindings:
    Arrow keys  → UP / DOWN / LEFT / RIGHT
    Enter       → SELECT
    Esc         → BACK
    m           → MENU
    q           → QUIT
"""
from __future__ import annotations
import queue
import signal
import sys
import termios
import threading
import tty
from PIL import Image
from hal.display_base import DisplayBase
from hal.input_base import Button, ButtonEvent


# ANSI escape sequence → Button mapping
_KEY_MAP: dict[str, Button] = {
    "\x1b[A": Button.UP,
    "\x1b[B": Button.DOWN,
    "\x1b[D": Button.LEFT,
    "\x1b[C": Button.RIGHT,
    "\r":     Button.SELECT,
    "\n":     Button.SELECT,
    "\x1b":   Button.BACK,
    "m":      Button.MENU,
}


class RpiSshDisplay(DisplayBase):
    """E-ink display with keyboard input read from stdin (SSH terminal)."""

    FULL_REFRESH_INTERVAL = 100

    def __init__(self) -> None:
        self._event_queue: queue.Queue[ButtonEvent] = queue.Queue()
        self._running = True
        self._fast_count = 0

        self._epd = self._init_display()
        self._start_keyboard_thread()

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    # ------------------------------------------------------------------
    # DisplayBase interface
    # ------------------------------------------------------------------

    def show(self, image: Image.Image) -> None:
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
    # Input
    # ------------------------------------------------------------------

    def poll_event(self) -> ButtonEvent | None:
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
    # Internal — keyboard (raw terminal mode)
    # ------------------------------------------------------------------

    def _start_keyboard_thread(self) -> None:
        self._old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        t = threading.Thread(target=self._read_keys, daemon=True)
        t.start()

    def _read_keys(self) -> None:
        """Read keypresses from stdin in raw mode on a background thread."""
        while self._running:
            try:
                ch = sys.stdin.read(1)
                if not ch:
                    continue

                # Build up escape sequences (arrow keys send 3 bytes)
                if ch == "\x1b":
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        ch3 = sys.stdin.read(1)
                        seq = ch + ch2 + ch3
                        btn = _KEY_MAP.get(seq)
                    else:
                        # Bare Esc
                        btn = _KEY_MAP.get("\x1b")
                elif ch == "q":
                    self._shutdown()
                    break
                else:
                    btn = _KEY_MAP.get(ch)

                if btn is not None:
                    self._event_queue.put(ButtonEvent(button=btn, pressed=True))
                    self._event_queue.put(ButtonEvent(button=btn, pressed=False))
            except Exception:
                break

    # ------------------------------------------------------------------
    # Internal — shutdown
    # ------------------------------------------------------------------

    def _shutdown(self, *_) -> None:
        self._running = False
        # Restore terminal settings
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
        except Exception:
            pass
        try:
            self._epd.sleep()
        except Exception:
            pass
