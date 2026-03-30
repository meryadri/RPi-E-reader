"""
EPUB parsing layer.
Extracts ordered chapters as plain text, publication year, and cover image.

Text extraction notes:
  - Spine order is used so chapters appear in reading order.
  - Headings (h1–h6) flow as regular paragraphs; no separate chapter title
    metadata is needed since the headings are already in the text stream.
  - <a epub:type="noteref"> markers are formatted as [n] so footnote/endnote
    references are visible inline.
  - <a role="doc-backlink"> navigation arrows (↩︎) are suppressed.
  - <sup> content is formatted as [n].
  - <img> and <figure> become [Figure: caption/alt] placeholders.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class Chapter:
    title: str
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class ParsedBook:
    title: str
    author: str
    year: str = ""
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def full_text_paragraphs(self) -> list[str]:
        result = []
        for ch in self.chapters:
            if ch.title:
                result.append(f"\n{ch.title}\n")
            result.extend(ch.paragraphs)
        return result


def _node_to_text(node) -> str:
    """Recursively convert a BS4 node to plain text with inline formatting."""
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
        # Suppress back-navigation arrows (↩︎)
        if "backlink" in epub_type or "backlink" in role or "backlink" in cls:
            return ""
        # Format footnote/endnote reference markers as [n]
        if "noteref" in epub_type or "noteref" in role or "noteref" in cls:
            inner = "".join(_node_to_text(c) for c in node.children).strip()
            return f"[{inner}]" if inner else ""

    if name == "br":
        return " "

    return "".join(_node_to_text(c) for c in node.children)


_BLOCK = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "figure"})


def _html_to_paragraphs(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    paragraphs = []
    for tag in soup.find_all(_BLOCK):
        # Skip elements nested inside another block we will process
        if any(p.name in _BLOCK for p in tag.parents):
            continue

        if tag.name == "figure":
            img = tag.find("img")
            if not img:
                continue
            cap = tag.find("figcaption")
            label = (cap.get_text(strip=True) if cap else "") or (img.get("alt") or "").strip()
            paragraphs.append(f"[Figure: {label}]" if label else "[Figure]")
        else:
            text = " ".join(_node_to_text(tag).split())
            if text:
                paragraphs.append(text)

    return paragraphs


def parse_epub(filepath: str | Path) -> ParsedBook:
    book = epub.read_epub(str(filepath))

    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else Path(filepath).stem

    author = book.get_metadata("DC", "creator")
    author = author[0][0] if author else "Unknown"

    date = book.get_metadata("DC", "date")
    year = date[0][0][:4] if date else ""

    # Iterate in spine order so chapters appear in reading order.
    # Chapter titles are left empty — h1–h6 headings flow as paragraphs.
    chapters: list[Chapter] = []
    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item is None:
            continue
        paras = _html_to_paragraphs(item.get_content())
        if not paras:
            continue
        chapters.append(Chapter(title="", paragraphs=paras))

    return ParsedBook(title=title, author=author, year=year, chapters=chapters)


def extract_cover_image(filepath: str | Path) -> bytes | None:
    """Return raw bytes of the cover image, or None if not found."""
    book = epub.read_epub(str(filepath))

    # Method 1: OPF <meta name="cover" content="id"/>
    for meta in book.get_metadata("OPF", "meta"):
        attrs = meta[1] if len(meta) > 1 else {}
        if attrs.get("name") == "cover":
            item = book.get_item_with_id(attrs.get("content", ""))
            if item:
                return item.get_content()

    # Method 2: dedicated ITEM_COVER entries
    for item in book.get_items_of_type(ebooklib.ITEM_COVER):
        return item.get_content()

    # Method 3: first image in the book
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        return item.get_content()

    return None
