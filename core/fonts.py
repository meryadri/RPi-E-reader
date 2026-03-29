"""
Central font loader — all screens import from here.

Two font families:
  COMMIT_MONO  — the bundled CommitMono typeface (default)
  SYSTEM       — DejaVu Sans on Linux/Pi, Arial on macOS, fallback otherwise
"""
from pathlib import Path
from PIL import ImageFont

COMMIT_MONO = "commit_mono"
SYSTEM      = "system"

_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_COMMIT_MONO_FILES = {
    (False, False): "CommitMonoAdrienEreader-400-Regular.otf",
    (False, True):  "CommitMonoAdrienEreader-400-Italic.otf",
    (True,  False): "CommitMonoAdrienEreader-700-Regular.otf",
    (True,  True):  "CommitMonoAdrienEreader-700-Italic.otf",
}

# Ordered candidate paths tried left-to-right for system font.
# DejaVu ships with Raspberry Pi OS; Arial is present on macOS.
_SYSTEM_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]
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
    return _load_commit_mono(size, bold, italic)


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
