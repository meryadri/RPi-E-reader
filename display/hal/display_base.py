"""
Hardware Abstraction Layer — Display interface.
All display backends implement this interface.

Dimensions are per-instance (not class constants) so the same backend can be
driven in portrait (e-reader, 480×800) or landscape (dashboard, 800×480).
"""
from abc import ABC, abstractmethod
from PIL import Image


class DisplayBase(ABC):
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # Refresh hint — backends that support partial refresh can use this.
        # "partial" = flicker-free (page turns), "full" = clean redraw (screen switches).
        self._refresh_hint: str = "full"

    def set_refresh_hint(self, hint: str) -> None:
        self._refresh_hint = hint

    @abstractmethod
    def show(self, image: Image.Image) -> None:
        """Push a Pillow image to the display."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear the display to white."""
        ...
