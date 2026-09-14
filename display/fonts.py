"""
Central font loader — all screens import from here.

Font families:
  COMMIT_MONO  — the bundled CommitMono typeface (default)
  SYSTEM       — DejaVu Sans on Linux/Pi, Arial on macOS, fallback otherwise
  WEATHER      — Weather Icons (erikflowers), an icon font; see weather_icons.py
"""
from pathlib import Path
from PIL import ImageFont

COMMIT_MONO = "commit_mono"
SYSTEM      = "system"
WEATHER     = "weather"

_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_COMMIT_MONO_FILES = {
    (False, False): "CommitMono-400-Regular.otf",
    (False, True):  "CommitMono-400-Italic.otf",
    (True,  False): "CommitMono-700-Regular.otf",
    (True,  True):  "CommitMono-700-Italic.otf",
}

# Ordered candidate paths tried left-to-right for system font.
# DejaVu ships with Raspberry Pi OS; Arial is present on macOS.
_SYSTEM_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]
# Weather Icons 2.0 by Erik Flowers — SIL OFL 1.1.
# https://github.com/erikflowers/weather-icons
_WEATHER_FILE = "weathericons-regular-webfont.ttf"

_SYSTEM_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def load(
    size: int,
    bold: bool = False,
    italic: bool = False,
    font_name: str = COMMIT_MONO,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_name == SYSTEM:
        return _load_system(size, bold)
    if font_name == WEATHER:
        return _load_weather(size)
    return _load_commit_mono(size, bold, italic)


def _load_weather(size: int):
    """The weather icon font, or None if it is not bundled.

    Returns None rather than a fallback font: a text fallback would draw a tofu
    box where an icon belongs, so callers use this to decide whether to draw
    glyph icons or fall back to hand-drawn shapes.
    """
    try:
        return ImageFont.truetype(str(_DIR / _WEATHER_FILE), size)
    except Exception:
        return None


def _load_commit_mono(size: int, bold: bool, italic: bool):
    try:
        return ImageFont.truetype(str(_DIR / _COMMIT_MONO_FILES[(bold, italic)]), size)
    except Exception:
        return _fallback(size)


def _load_system(size: int, bold: bool):
    for path in (_SYSTEM_BOLD if bold else _SYSTEM_REGULAR):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return _fallback(size)


def _fallback(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()
