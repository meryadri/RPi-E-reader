"""
Renderer — turns a Page object into a Pillow image.
"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
from core.paginator import Page, FONT_PATH, DEFAULT_FONT_SIZE, MARGIN_X, MARGIN_Y, LINE_SPACING
from hal.display_base import DisplayBase


BG_COLOR = "white"
FG_COLOR = "black"
STATUS_COLOR = (100, 100, 100)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


def render_page(
    page: Page,
    total_pages: int,
    book_title: str = "",
    font_size: int = DEFAULT_FONT_SIZE,
    width: int = DisplayBase.WIDTH,
    height: int = DisplayBase.HEIGHT,
) -> Image.Image:
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)

    bbox_sample = font.getbbox("Ag")
    line_height = (bbox_sample[3] - bbox_sample[1]) + LINE_SPACING

    y = MARGIN_Y
    for line in page.lines:
        draw.text((MARGIN_X, y), line, font=font, fill=FG_COLOR)
        y += line_height

    # Status bar at bottom
    status = f"{book_title}  |  {page.page_number + 1} / {total_pages}"
    draw.text((MARGIN_X, height - 28), status, font=font, fill=STATUS_COLOR)
    # Thin separator line
    draw.line([(MARGIN_X, height - 34), (width - MARGIN_X, height - 34)], fill=STATUS_COLOR, width=1)

    return img
