"""
Display runtime — the app-agnostic core.

Provides:
  - Screen        : base class for a single drawable screen
  - StateMachine  : owns the active screen, redraws on demand
  - App           : bundles orientation + root screen + input policy for one app
  - run()         : the shared main loop (replaces the old per-backend main_*.py)

Orientation is expressed as a logical (width, height):
  PORTRAIT  = (480, 800)   e-reader
  LANDSCAPE = (800, 480)   dashboard
The physical panel is 800×480; a portrait app renders 480×800 and the HAL
handles the rest.
"""
from __future__ import annotations
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw

from display.hal.display_base import DisplayBase
from display.hal.input_base import ButtonEvent

PORTRAIT: tuple[int, int] = (480, 800)
LANDSCAPE: tuple[int, int] = (800, 480)


class Screen(ABC):
    def __init__(self, state_machine: "StateMachine"):
        self.sm = state_machine
        # Dimensions come from the active display (per-app orientation), so
        # screen layout code can keep using self.WIDTH / self.HEIGHT.
        self.WIDTH = state_machine.width
        self.HEIGHT = state_machine.height

    @abstractmethod
    def render(self) -> Image.Image:
        """Return a WIDTH×HEIGHT RGB Pillow image representing this screen."""
        ...

    @abstractmethod
    def handle(self, event: ButtonEvent) -> None:
        """React to a button event.  Call self.sm.switch(screen) to navigate."""
        ...

    def on_enter(self) -> None:
        """Called when this screen becomes active."""

    def on_exit(self) -> None:
        """Called when leaving this screen."""

    def poll(self) -> None:
        """Called every frame (no event required).

        Override to drive timer-based redraws — e.g. a clock that calls
        self.sm.mark_dirty() when the displayed minute changes.
        """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def blank_canvas(self, color: str = "white") -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color)
        draw = ImageDraw.Draw(img)
        return img, draw


class StateMachine:
    def __init__(self, display: DisplayBase):
        self._display = display
        self.width = display.width
        self.height = display.height
        self._current: Screen | None = None
        self._dirty = True

    def switch(self, screen: Screen) -> None:
        if self._current:
            self._current.on_exit()
        self._current = screen
        screen.on_enter()
        self._dirty = True
        self._display.set_refresh_hint("full")

    def mark_dirty(self, hint: str = "partial") -> None:
        self._dirty = True
        self._display.set_refresh_hint(hint)

    def tick(self, event: ButtonEvent | None) -> None:
        """Process one event (may be None) and redraw if needed."""
        if self._current is None:
            return
        if event:
            self._current.handle(event)
        self._current.poll()
        if self._dirty:
            img = self._current.render()
            self._display.show(img)
            self._dirty = False


@dataclass
class App:
    """Describes one application the launcher can run."""
    name: str
    size: tuple[int, int]                              # PORTRAIT or LANDSCAPE
    build_root: Callable[[StateMachine], Screen]       # builds the first screen
    uses_input: bool = True                            # False = no buttons (dashboard)
    setup: Callable[[], None] | None = None            # one-time init (e.g. init_db)


def run(app: App, display: DisplayBase, target_fps: int = 30) -> None:
    """Shared main loop.  Runs until the display reports it is no longer running."""
    if app.setup:
        app.setup()

    sm = StateMachine(display)
    sm.switch(app.build_root(sm))

    frame_time = 1.0 / target_fps
    while display.is_running():
        t0 = time.monotonic()
        event = display.poll_event()
        sm.tick(event)
        sleep = frame_time - (time.monotonic() - t0)
        if sleep > 0:
            time.sleep(sleep)
