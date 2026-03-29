"""
Paginator — splits a flat list of paragraphs into display pages.
Each page is a list of lines that fit within the given dimensions at the given font size.
"""
from __future__ import annotations
from dataclasses import dataclass
from core import fonts

DEFAULT_FONT_SIZE = 16
FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 32
LINE_SPACING = 8
MARGIN_X = 30
MARGIN_Y = 44


@dataclass
class Page:
    lines: list[str]
    page_number: int       # 0-based


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = font.getbbox(candidate)
        if bbox[2] - bbox[0] <= max_width:
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
    font_name: str = fonts.COMMIT_MONO,
) -> list[Page]:
    font = fonts.load(font_size, font_name=font_name)
    bbox_sample = font.getbbox("Ag")
    line_height = (bbox_sample[3] - bbox_sample[1]) + LINE_SPACING

    max_width = display_width - 2 * MARGIN_X
    # Reserve bottom 40 px for the status bar
    max_lines = (display_height - MARGIN_Y - 40) // line_height

    pages: list[Page] = []
    current_lines: list[str] = []

    for para in paragraphs:
        wrapped = _wrap_text(para, font, max_width)
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
