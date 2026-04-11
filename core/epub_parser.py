"""
EPUB parsing layer.
Extracts ordered chapters as plain text/images, publication year, and cover image.

Text extraction notes:
  - Spine order is used so chapters appear in reading order.
  - Headings (h1–h6) flow as regular paragraphs.
  - Block-level <img> and <figure> elements become ImageBlock objects so the
    renderer can paste the actual image; inline <img> within <p> fall back to
    a "[Image: alt]" text placeholder.
  - <li> items with inline-only content (TOC entries) are kept as paragraphs.
  - <a epub:type="noteref"> markers are formatted as [n].
  - <a role="doc-backlink"> navigation arrows are suppressed.
  - <sup> content is formatted as [n].
  - <br> tags split the enclosing paragraph into separate paragraphs.
"""
from __future__ import annotations
import posixpath
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image as PILImage

from core.paginator import ImageBlock, MARGIN_X, MARGIN_Y


@dataclass
class Chapter:
    title: str
    paragraphs: list[str | ImageBlock] = field(default_factory=list)


@dataclass
class ParsedBook:
    title: str
    author: str
    year: str = ""
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def full_text_paragraphs(self) -> list[str | ImageBlock]:
        result: list[str | ImageBlock] = []
        for ch in self.chapters:
            if ch.title:
                result.append(f"\n{ch.title}\n")
            result.extend(ch.paragraphs)
        return result


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _make_image_block(
    src: str,
    doc_file_name: str,
    img_map: dict[str, bytes],
    display_width: int,
    display_height: int,
) -> ImageBlock | None:
    """Resolve an <img src="..."> to a pre-scaled ImageBlock, or None."""
    if not src:
        return None
    base = posixpath.dirname(doc_file_name)
    resolved = posixpath.normpath(posixpath.join(base, src))
    raw = img_map.get(resolved)
    if raw is None:
        return None
    try:
        pil = PILImage.open(BytesIO(raw))
        pil.load()   # force decode — BytesIO can be GC'd otherwise
    except Exception:
        return None

    orig_w, orig_h = pil.size
    if orig_w <= 0 or orig_h <= 0:
        return None

    max_w = display_width - 2 * MARGIN_X
    max_h = display_height - MARGIN_Y - 40
    scale = min(max_w / orig_w, max_h / orig_h, 1.0)   # never upscale
    scaled_w = max(1, int(orig_w * scale))
    scaled_h = max(1, int(orig_h * scale))

    if scaled_w != orig_w or scaled_h != orig_h:
        pil = pil.resize((scaled_w, scaled_h), PILImage.LANCZOS)

    # Composite onto white background for images with transparency
    if pil.mode in ("RGBA", "LA", "PA"):
        bg = PILImage.new("RGB", pil.size, "white")
        bg.paste(pil, mask=pil.split()[-1])
        pil = bg
    elif pil.mode != "RGB":
        pil = pil.convert("RGB")

    return ImageBlock(image=pil, scaled_width=scaled_w, scaled_height=scaled_h)


# ---------------------------------------------------------------------------
# HTML → paragraph extraction
# ---------------------------------------------------------------------------

def _node_to_text(node) -> str:
    """Recursively convert a BS4 node to plain text with inline formatting.

    Inline <img> within <p> fall back to text placeholders.
    Returns a string that may contain '\\n' at <br> positions; callers split
    on '\\n' to produce separate paragraphs.
    """
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name

    if name in ("script", "style"):
        return ""

    if name == "img":
        alt = (node.get("alt") or "").strip()
        return f"[Image: {alt}]" if alt else "[Image]"

    if name == "sup":
        inner = "".join(_node_to_text(c) for c in node.children).strip()
        return f"[{inner}]" if inner else ""

    if name == "a":
        epub_type = node.get("epub:type") or node.get("epub_type") or ""
        role      = node.get("role") or ""
        cls       = " ".join(node.get("class") or [])
        if "backlink" in epub_type or "backlink" in role or "backlink" in cls:
            return ""
        if "noteref" in epub_type or "noteref" in role or "noteref" in cls:
            inner = "".join(_node_to_text(c) for c in node.children).strip()
            return f"[{inner}]" if inner else ""

    if name == "br":
        return "\n"

    return "".join(_node_to_text(c) for c in node.children)


_BLOCK = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "figure", "img"})


def _add_text_tag(tag: Tag, paragraphs: list) -> None:
    """Convert a tag's inline content and append resulting paragraphs."""
    raw = _node_to_text(tag)
    for part in raw.split("\n"):
        text = " ".join(part.split())
        if text:
            paragraphs.append(text)


def _html_to_paragraphs(
    html: bytes,
    img_map: dict[str, bytes],
    doc_file_name: str,
    display_width: int,
    display_height: int,
) -> list[str | ImageBlock]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    paragraphs: list[str | ImageBlock] = []

    for tag in soup.find_all(_BLOCK | {"li"}):
        # Skip elements nested inside a block we will process
        if any(p.name in _BLOCK for p in tag.parents):
            continue

        if tag.name == "figure":
            img_tag = tag.find("img")
            if not img_tag:
                continue
            block = _make_image_block(
                img_tag.get("src") or "", doc_file_name, img_map,
                display_width, display_height,
            )
            if block:
                paragraphs.append(block)
            else:
                cap = tag.find("figcaption")
                label = (cap.get_text(strip=True) if cap else "") or (img_tag.get("alt") or "").strip()
                paragraphs.append(f"[Figure: {label}]" if label else "[Figure]")

        elif tag.name == "img":
            # Standalone <img> not inside any block we handle
            if any(p.name in (_BLOCK | {"li"}) for p in tag.parents):
                continue
            block = _make_image_block(
                tag.get("src") or "", doc_file_name, img_map,
                display_width, display_height,
            )
            if block:
                paragraphs.append(block)

        elif tag.name == "li":
            # Only process <li> with inline-only content (TOC entries etc.)
            if any(c.name in _BLOCK for c in tag.children if isinstance(c, Tag)):
                continue
            _add_text_tag(tag, paragraphs)

        else:
            _add_text_tag(tag, paragraphs)

    return paragraphs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_epub(filepath: str | Path) -> ParsedBook:
    book = epub.read_epub(str(filepath))

    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else Path(filepath).stem

    author = book.get_metadata("DC", "creator")
    author = author[0][0] if author else "Unknown"

    date = book.get_metadata("DC", "date")
    year = date[0][0][:4] if date else ""

    # Build image lookup map once — keyed by file_name as it appears in the OPF
    img_map: dict[str, bytes] = {
        item.file_name: item.get_content()
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE)
    }

    chapters: list[Chapter] = []
    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item is None:
            continue
        paras = _html_to_paragraphs(
            item.get_content(),
            img_map=img_map,
            doc_file_name=item.file_name,
            display_width=480,
            display_height=800,
        )
        if not paras:
            continue
        chapters.append(Chapter(title="", paragraphs=paras))

    return ParsedBook(title=title, author=author, year=year, chapters=chapters)


def extract_cover_image(filepath: str | Path) -> bytes | None:
    """Return raw bytes of the cover image, or None if not found."""
    book = epub.read_epub(str(filepath))

    for meta in book.get_metadata("OPF", "meta"):
        attrs = meta[1] if len(meta) > 1 else {}
        if attrs.get("name") == "cover":
            item = book.get_item_with_id(attrs.get("content", ""))
            if item:
                return item.get_content()

    for item in book.get_items_of_type(ebooklib.ITEM_COVER):
        return item.get_content()

    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        return item.get_content()

    return None
