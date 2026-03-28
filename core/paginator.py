"""
Paginator — splits a flat list of paragraphs into display pages.
Each page is a list of lines that fit within the given dimensions at the given font size.
"""
from __future__ import annotations
from dataclasses import dataclass
from PIL import ImageFont

FONT_PATH = None          # None → Pillow default bitmap font
DEFAULT_FONT_SIZE = 20
LINE_SPACING = 6          # extra pixels between lines
MARGIN_X = 40
MARGIN_Y = 40


@dataclass
class Page:
    lines: list[str]
    page_number: int       # 0-based


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    """Word-wrap a single paragraph into lines that fit max_width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = font.getbbox(candidate)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def paginate(
    paragraphs: list[str],
    display_width: int = 480,
    display_height: int = 800,
    font_size: int = DEFAULT_FONT_SIZE,
) -> list[Page]:
    font = _load_font(font_size)
    bbox_sample = font.getbbox("Ag")
    line_height = (bbox_sample[3] - bbox_sample[1]) + LINE_SPACING

    max_width = display_width - 2 * MARGIN_X
    max_lines = (display_height - 2 * MARGIN_Y) // line_height

    pages: list[Page] = []
    current_lines: list[str] = []

    for para in paragraphs:
        wrapped = _wrap_text(para, font, max_width)
        # blank line between paragraphs
        if current_lines:
            wrapped = [""] + wrapped

        for line in wrapped:
            current_lines.append(line)
            if len(current_lines) >= max_lines:
                pages.append(Page(lines=current_lines[:], page_number=len(pages)))
                current_lines = []

    if current_lines:
        pages.append(Page(lines=current_lines, page_number=len(pages)))

    return pages
