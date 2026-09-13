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
from display.hal.display_base import DisplayBase
from display.hal.input_base import Button, ButtonEvent


# Physical diagonal of the 7.5" e-ink panel. The physical width/height (in
# inches) are derived per-instance from the logical (width, height) aspect,
# so a portrait 480×800 app yields a tall window and a landscape 800×480 app
# a wide one.
_DIAG_IN = 7.5


def _screen_dpi() -> float:
    """Return the logical DPI of the primary screen.

    Uses CoreGraphics on macOS.
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

# Window events after which macOS/SDL may have discarded the window's contents.
#
# SDL documents the backbuffer as undefined once it has been presented, so the
# last frame is not guaranteed to survive an occlusion, a Space switch, or a
# minimise/restore.  The app has to re-present it; nothing does that for us.
#
# getattr guards: WINDOW* were added in pygame 2, and this module is the only
# one that would break on an older pygame.
_REDRAW_EVENTS = frozenset(
    e for e in (
        getattr(pygame, "VIDEOEXPOSE", None),
        getattr(pygame, "WINDOWEXPOSED", None),
        getattr(pygame, "WINDOWSHOWN", None),
        getattr(pygame, "WINDOWRESTORED", None),
        getattr(pygame, "WINDOWMAXIMIZED", None),
        getattr(pygame, "WINDOWFOCUSGAINED", None),
    ) if e is not None
)

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

    def __init__(self, width: int, height: int):
        super().__init__(width, height)

        # Read DPI before pygame.init() — on macOS, SDL takes over the ObjC
        # app context and tkinter crashes if initialised afterwards.
        dpi = _screen_dpi()
        pygame.init()

        # Physical inches derived from the logical aspect (7.5" diagonal panel).
        diag_px = math.hypot(width, height)
        phys_w_in = _DIAG_IN * width / diag_px
        phys_h_in = _DIAG_IN * height / diag_px

        # Window size = physical inches × screen DPI, rounded to whole pixels
        self._win_w = round(phys_w_in * dpi)
        self._win_h = round(phys_h_in * dpi)

        self._screen = pygame.display.set_mode((self._win_w, self._win_h))
        pygame.display.set_caption(
            f"E-ink Simulator  —  {self._win_w}×{self._win_h} px  "
            f"({phys_w_in:.2f}\" × {phys_h_in:.2f}\"  @  {dpi:.0f} dpi)"
        )
        self._event_queue: queue.Queue[ButtonEvent] = queue.Queue()
        self._running = True

        # The most recently shown frame, kept so an expose event can repaint the
        # window.  None means "blank white".
        self._last_frame: pygame.Surface | None = None

        # Show a blank white screen on start
        self._present()

    # ------------------------------------------------------------------
    # DisplayBase interface
    # ------------------------------------------------------------------

    def show(self, image: Image.Image) -> None:
        """Scale the rendered Pillow image to the physical window size and blit it."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        # Scale rendered content to match the physical window dimensions
        if (self._win_w, self._win_h) != (self.width, self.height):
            image = image.resize((self._win_w, self._win_h), Image.LANCZOS)
        raw = image.tobytes()
        self._last_frame = pygame.image.fromstring(
            raw, (self._win_w, self._win_h), "RGB"
        )
        self._present()
        self._pump_events()

    def clear(self) -> None:
        self._last_frame = None
        self._present()
        self._pump_events()

    def _present(self) -> None:
        """Blit the last frame to the window and flip.

        Deliberately does NOT pump events: it is called *from* _pump_events()
        to service an expose, and pumping there would recurse.
        """
        if self._last_frame is None:
            self._screen.fill((255, 255, 255))
        else:
            self._screen.blit(self._last_frame, (0, 0))
        pygame.display.flip()

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
            elif event.type in _REDRAW_EVENTS:
                # Repaint from our own copy rather than marking the screen
                # dirty: the app decides when content changes, and a dashboard
                # that only redraws once a minute would otherwise show a black
                # window until the next tick.
                self._present()
