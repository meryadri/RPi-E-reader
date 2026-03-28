"""
Hardware Abstraction Layer — Display interface.
All display backends implement this interface.
"""
from abc import ABC, abstractmethod
from PIL import Image


class DisplayBase(ABC):
    WIDTH = 480
    HEIGHT = 800

    @abstractmethod
    def show(self, image: Image.Image) -> None:
        """Push a Pillow image to the display."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear the display to white."""
        ...
