"""
Central font loader — all screens import from here.
Falls back to Pillow's built-in font if the file is missing.
"""
from pathlib import Path
from PIL import ImageFont

_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_FILES = {
    (False, False): "CommitMonoadrien-400-Regular.otf",
    (False, True):  "CommitMonoadrien-400-Italic.otf",
    (True,  False): "CommitMonoadrien-700-Regular.otf",
    (True,  True):  "CommitMonoadrien-700-Italic.otf",
}


def load(
    size: int,
    bold: bool = False,
    italic: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _DIR / _FILES[(bold, italic)]
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()
