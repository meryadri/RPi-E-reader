"""
Renderer — turns a Page object into a Pillow image.
"""
from __future__ import annotations
from PIL import Image, ImageDraw
from core import fonts
from core.paginator import Page, DEFAULT_FONT_SIZE, MARGIN_X, MARGIN_Y, LINE_SPACING
from hal.display_base import DisplayBase


BG_COLOR = "white"
FG_COLOR = "black"
STATUS_COLOR = (120, 120, 120)


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
    font = fonts.load(font_size)

    bbox_sample = font.getbbox("Ag")
    line_height = (bbox_sample[3] - bbox_sample[1]) + LINE_SPACING

    y = MARGIN_Y
    for line in page.lines:
        draw.text((MARGIN_X, y), line, font=font, fill=FG_COLOR)
        y += line_height

    # Status bar
    status_font = fonts.load(max(12, font_size - 6))
    pct = (page.page_number + 1) / max(1, total_pages)
    bar_y = height - 32
    draw.line([(MARGIN_X, bar_y), (width - MARGIN_X, bar_y)], fill=(200, 200, 200), width=1)
    # Progress fill
    fill_w = int((width - 2 * MARGIN_X) * pct)
    draw.line([(MARGIN_X, bar_y), (MARGIN_X + fill_w, bar_y)], fill=(80, 80, 80), width=2)

    title_trunc = book_title[:28] + "…" if len(book_title) > 28 else book_title
    draw.text((MARGIN_X, bar_y + 6), title_trunc, font=status_font, fill=STATUS_COLOR)
    page_str = f"{page.page_number + 1}/{total_pages}"
    pbbox = status_font.getbbox(page_str)
    draw.text((width - MARGIN_X - (pbbox[2] - pbbox[0]), bar_y + 6), page_str, font=status_font, fill=STATUS_COLOR)

    return img
