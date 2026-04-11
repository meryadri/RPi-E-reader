"""
Paginator — splits a flat list of paragraphs into display pages.
Each page is a list of lines that fit within the given dimensions at the given font size.

Performance notes:
  - Word advance widths are stored in a persistent metrics cache keyed by
    (font_size, font_name).  Each unique word is measured at most once ever —
    results survive across calls and app restarts (data/metrics_cache.pkl).
  - Line width is tracked by addition rather than re-measuring the full string,
    reducing font calls from O(W²) to O(new_unique_words_in_this_book).
  - getlength() is preferred over getbbox() — skips the vertical bbox computation.

Image handling:
  - ImageBlock paragraphs are scaled by the parser to fit the content width.
    The paginator computes how many line-slots each image occupies and inserts
    padding sentinel strings ("\\x00") after the ImageBlock.  The renderer
    pastes the image and advances y by its pixel height; the sentinel slots
    are skipped so y is not double-advanced.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from PIL import Image as PILImage
from core import fonts
from core import metrics_cache

DEFAULT_FONT_SIZE = 16
FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 32
LINE_SPACING = 8
MARGIN_X = 30
MARGIN_Y = 44

# Sentinel appended after an ImageBlock to consume line-slot budget.
# Distinct from "" (paragraph separator) so the renderer can skip it.
IMAGE_PAD = "\x00"


@dataclass
class ImageBlock:
    """An image extracted from the EPUB, pre-scaled to fit the content width."""
    image: PILImage.Image
    scaled_width: int
    scaled_height: int
    slots: int = 0   # filled in by paginate(), not the parser


@dataclass
class Page:
    lines: list[str | ImageBlock]
    page_number: int       # 0-based


def _width(font, text: str) -> float:
    """Return the advance width of text in pixels."""
    try:
        return font.getlength(text)
    except AttributeError:
        bb = font.getbbox(text)
        return bb[2] - bb[0]


def _wrap_text(text: str, font, max_width: int, word_cache: dict) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    for word in words:
        if word not in word_cache:
            word_cache[word] = _width(font, word)

    space_w = word_cache[" "]

    lines:     list[str] = []
    current:   list[str] = []
    current_w: float     = 0.0

    for word in words:
        ww = word_cache[word]
        if not current:
            current   = [word]
            current_w = ww
        elif current_w + space_w + ww <= max_width:
            current.append(word)
            current_w += space_w + ww
        else:
            lines.append(" ".join(current))
            current   = [word]
            current_w = ww

    if current:
        lines.append(" ".join(current))

    return lines or [""]


def paginate(
    paragraphs: list[str | ImageBlock],
    display_width: int = 480,
    display_height: int = 800,
    font_size: int = DEFAULT_FONT_SIZE,
    font_name: str = fonts.COMMIT_MONO,
) -> list[Page]:
    font = fonts.load(font_size, font_name=font_name)
    bbox_sample = font.getbbox("Ag")
    line_height = (bbox_sample[3] - bbox_sample[1]) + LINE_SPACING

    max_width = display_width - 2 * MARGIN_X
    max_lines = (display_height - MARGIN_Y - 40) // line_height

    # Pre-compute slots for every ImageBlock.
    # Work on copies so the parsed book can be re-paginated at a different
    # font size without slots being stale from a prior call.
    processed: list[str | ImageBlock] = []
    for item in paragraphs:
        if isinstance(item, ImageBlock):
            slots = math.ceil(item.scaled_height / line_height)
            slots = min(slots, max_lines)   # never taller than one page
            item = ImageBlock(
                image=item.image,
                scaled_width=item.scaled_width,
                scaled_height=item.scaled_height,
                slots=slots,
            )
        processed.append(item)

    # Persistent word cache — shared across all calls with the same font config
    word_cache = metrics_cache.slot(font_size, font_name)
    size_before = len(word_cache)
    if " " not in word_cache:
        word_cache[" "] = _width(font, " ")

    pages:         list[Page]              = []
    current_lines: list[str | ImageBlock]  = []

    for item in processed:

        if isinstance(item, ImageBlock):
            # Flush current page if the image won't fit
            if current_lines and len(current_lines) + item.slots > max_lines:
                pages.append(Page(lines=current_lines, page_number=len(pages)))
                current_lines = []
            # Blank-line separator (same as text paragraphs)
            if current_lines:
                current_lines.append("")
            current_lines.append(item)
            # Padding sentinels consume the remaining slot budget
            for _ in range(item.slots - 1):
                current_lines.append(IMAGE_PAD)
            if len(current_lines) >= max_lines:
                pages.append(Page(lines=current_lines, page_number=len(pages)))
                current_lines = []
            continue

        wrapped = _wrap_text(item, font, max_width, word_cache)
        if current_lines:
            wrapped = [""] + wrapped

        for line in wrapped:
            current_lines.append(line)
            if len(current_lines) >= max_lines:
                pages.append(Page(lines=current_lines, page_number=len(pages)))
                current_lines = []

    if current_lines:
        pages.append(Page(lines=current_lines, page_number=len(pages)))

    # Persist any newly measured words to disk
    if len(word_cache) > size_before:
        metrics_cache.mark_dirty()
    metrics_cache.save()

    return pages
