"""
Hardware Abstraction Layer — Display interface.
All display backends implement this interface.
"""
from abc import ABC, abstractmethod
from PIL import Image


class DisplayBase(ABC):
    WIDTH = 480
    HEIGHT = 800

    # Refresh hint — backends that support partial refresh can use this.
    # "partial" = flicker-free (page turns), "full" = clean redraw (screen switches).
    _refresh_hint: str = "full"

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
