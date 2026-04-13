"""
Renderer — turns a Page object into a Pillow image.
"""
from __future__ import annotations
from PIL import Image, ImageDraw
from core import fonts
from core.paginator import Page, ImageBlock, IMAGE_PAD, DEFAULT_FONT_SIZE, MARGIN_X, MARGIN_Y, LINE_SPACING
from hal.display_base import DisplayBase


BG_COLOR = "white"
FG_COLOR = "black"
STATUS_COLOR = "black"


def render_page(
    page: Page,
    total_pages: int,
    book_title: str = "",
    font_size: int = DEFAULT_FONT_SIZE,
    font_name: str = fonts.COMMIT_MONO,
    width: int = DisplayBase.WIDTH,
    height: int = DisplayBase.HEIGHT,
) -> Image.Image:
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    font = fonts.load(font_size, font_name=font_name)

    bbox_sample = font.getbbox("Ag")
    line_height = (bbox_sample[3] - bbox_sample[1]) + LINE_SPACING
    max_width = width - 2 * MARGIN_X

    y = MARGIN_Y
    for line in page.lines:
        if isinstance(line, ImageBlock):
            paste_x = MARGIN_X + (max_width - line.scaled_width) // 2
            paste_img = line.image
            if paste_img.mode != "RGB":
                paste_img = paste_img.convert("RGB")
            img.paste(paste_img, (paste_x, y))
            y += line.scaled_height
        elif line == IMAGE_PAD:
            pass
        else:
            if line:
                draw.text((MARGIN_X, y), line, font=font, fill=FG_COLOR)
            y += line_height

    # Status bar
    status_font = fonts.load(max(12, font_size - 4))
    pct = (page.page_number + 1) / max(1, total_pages)
    bar_y = height - 36
    draw.line([(MARGIN_X, bar_y), (width - MARGIN_X, bar_y)], fill="black", width=1)
    # Progress fill
    fill_w = int((width - 2 * MARGIN_X) * pct)
    draw.line([(MARGIN_X, bar_y), (MARGIN_X + fill_w, bar_y)], fill="black", width=2)

    title_trunc = book_title[:34] + "…" if len(book_title) > 34 else book_title
    draw.text((MARGIN_X, bar_y + 8), title_trunc, font=status_font, fill=STATUS_COLOR)
    page_str = f"{page.page_number + 1}/{total_pages}"
    pbbox = status_font.getbbox(page_str)
    draw.text((width - MARGIN_X - (pbbox[2] - pbbox[0]), bar_y + 8), page_str, font=status_font, fill=STATUS_COLOR)

    return img
