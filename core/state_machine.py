"""
Screen state machine.
Each screen is a self-contained object that knows how to:
  - render itself to a Pillow image
  - handle a ButtonEvent and optionally return a transition
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw
from hal.display_base import DisplayBase
from hal.input_base import ButtonEvent


class Screen(ABC):
    WIDTH = DisplayBase.WIDTH
    HEIGHT = DisplayBase.HEIGHT

    def __init__(self, state_machine: "StateMachine"):
        self.sm = state_machine

    @abstractmethod
    def render(self) -> Image.Image:
        """Return an 800×480 RGB Pillow image representing this screen."""
        ...

    @abstractmethod
    def handle(self, event: ButtonEvent) -> None:
        """React to a button event.  Call self.sm.switch(screen) to navigate."""
        ...

    def on_enter(self) -> None:
        """Called when this screen becomes active."""

    def on_exit(self) -> None:
        """Called when leaving this screen."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def blank_canvas(self, color: str = "white") -> tuple[Image.Image, ImageDraw.Draw]:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color)
        draw = ImageDraw.Draw(img)
        return img, draw


class StateMachine:
    def __init__(self, display: DisplayBase):
        self._display = display
        self._current: Screen | None = None
        self._dirty = True

    def switch(self, screen: Screen) -> None:
        if self._current:
            self._current.on_exit()
        self._current = screen
        screen.on_enter()
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def tick(self, event: ButtonEvent | None) -> None:
        """Process one event (may be None) and redraw if needed."""
        if self._current is None:
            return
        if event:
            self._current.handle(event)
        if self._dirty:
            img = self._current.render()
            self._display.show(img)
            self._dirty = False
