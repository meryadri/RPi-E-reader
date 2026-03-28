"""
Hardware Abstraction Layer — Input interface.
Button event constants shared by all input backends.
"""
from dataclasses import dataclass
from enum import Enum, auto


class Button(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    SELECT = auto()
    BACK = auto()
    MENU = auto()


@dataclass
class ButtonEvent:
    button: Button
    pressed: bool  # True = press, False = release
