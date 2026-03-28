"""
Laptop simulator backend.
Renders to a pygame window and maps keyboard keys to button events.

The window is sized to match the physical dimensions of the real 7.5" e-ink
screen so proportions look correct on your laptop.
"""
import ctypes
import ctypes.util
import math
import platform
import queue
import pygame
from PIL import Image
from hal.display_base import DisplayBase
from hal.input_base import Button, ButtonEvent


# Physical size of the 7.5" 800×480 e-ink panel.
# diagonal = 7.5", aspect = 800:480  →  width ≈ 6.43", height ≈ 3.86"
_DIAG_IN = 7.5
_DIAG_PX = math.hypot(DisplayBase.WIDTH, DisplayBase.HEIGHT)
PHYSICAL_W_IN = _DIAG_IN * DisplayBase.WIDTH  / _DIAG_PX   # ≈ 6.43"
PHYSICAL_H_IN = _DIAG_IN * DisplayBase.HEIGHT / _DIAG_PX   # ≈ 3.86"


def _screen_dpi() -> float:
    """Return the logical DPI of the primary screen.

    Uses CoreGraphics on macOS (no tkinter, no SDL conflict).
    Falls back to 96 on other platforms.
    """
    if platform.system() == "Darwin":
        try:
            cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))

            class _CGSize(ctypes.Structure):
                _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

            class _CGPoint(ctypes.Structure):
                _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

            class _CGRect(ctypes.Structure):
                _fields_ = [("origin", _CGPoint), ("size", _CGSize)]

            cg.CGMainDisplayID.restype = ctypes.c_uint32
            cg.CGDisplayScreenSize.restype = _CGSize   # physical size in mm
            cg.CGDisplayBounds.restype = _CGRect        # logical pixel bounds

            display = cg.CGMainDisplayID()
            size_mm = cg.CGDisplayScreenSize(display)
            bounds = cg.CGDisplayBounds(display)

            logical_w = bounds.size.width
            physical_w_in = size_mm.width / 25.4       # mm → inches

            if physical_w_in > 0 and logical_w > 0:
                return logical_w / physical_w_in
        except Exception:
            pass
    return 96.0  # safe fallback for Linux / Windows

# Keyboard → Button mapping
KEY_MAP = {
    pygame.K_UP:     Button.UP,
    pygame.K_DOWN:   Button.DOWN,
    pygame.K_LEFT:   Button.LEFT,
    pygame.K_RIGHT:  Button.RIGHT,
    pygame.K_RETURN: Button.SELECT,
    pygame.K_ESCAPE: Button.BACK,
    pygame.K_m:      Button.MENU,
}


class SimulatorDisplay(DisplayBase):
    """Pygame-backed display that also pumps keyboard events into a queue."""

    def __init__(self):
        # Read DPI before pygame.init() — on macOS, SDL takes over the ObjC
        # app context and tkinter crashes if initialised afterwards.
        dpi = _screen_dpi()
        pygame.init()

        # Window size = physical inches × screen DPI, rounded to whole pixels
        self._win_w = round(PHYSICAL_W_IN * dpi)
        self._win_h = round(PHYSICAL_H_IN * dpi)

        self._screen = pygame.display.set_mode((self._win_w, self._win_h))
        pygame.display.set_caption(
            f"RPi E-Reader Simulator  —  {self._win_w}×{self._win_h} px  "
            f"({PHYSICAL_W_IN:.2f}\" × {PHYSICAL_H_IN:.2f}\"  @  {dpi:.0f} dpi)"
        )
        self._event_queue: queue.Queue[ButtonEvent] = queue.Queue()
        self._running = True

        # Show a blank white screen on start
        self._screen.fill((255, 255, 255))
        pygame.display.flip()

    # ------------------------------------------------------------------
    # DisplayBase interface
    # ------------------------------------------------------------------

    def show(self, image: Image.Image) -> None:
        """Scale the 800×480 Pillow image to the physical window size and blit it."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        # Scale rendered content to match the physical window dimensions
        if (self._win_w, self._win_h) != (self.WIDTH, self.HEIGHT):
            image = image.resize((self._win_w, self._win_h), Image.LANCZOS)
        raw = image.tobytes()
        surf = pygame.image.fromstring(raw, (self._win_w, self._win_h), "RGB")
        self._screen.blit(surf, (0, 0))
        pygame.display.flip()
        self._pump_events()

    def clear(self) -> None:
        self._screen.fill((255, 255, 255))
        pygame.display.flip()
        self._pump_events()

    @property
    def window_size(self) -> tuple[int, int]:
        """Actual pixel size of the simulator window."""
        return (self._win_w, self._win_h)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def poll_event(self) -> ButtonEvent | None:
        """Return the next queued button event, or None."""
        self._pump_events()
        try:
            return self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pump_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                btn = KEY_MAP.get(event.key)
                if btn:
                    self._event_queue.put(ButtonEvent(button=btn, pressed=True))
            elif event.type == pygame.KEYUP:
                btn = KEY_MAP.get(event.key)
                if btn:
                    self._event_queue.put(ButtonEvent(button=btn, pressed=False))
