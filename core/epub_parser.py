"""
EPUB parsing layer.
Extracts ordered chapters as plain text (with minimal formatting hints).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


@dataclass
class Chapter:
    title: str
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class ParsedBook:
    title: str
    author: str
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def full_text_paragraphs(self) -> list[str]:
        """Flat list of all paragraphs across all chapters."""
        result = []
        for ch in self.chapters:
            if ch.title:
                result.append(f"\n{ch.title}\n")
            result.extend(ch.paragraphs)
        return result


def _html_to_paragraphs(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = []
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4"]):
        text = tag.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)
    return paragraphs


def parse_epub(filepath: str | Path) -> ParsedBook:
    book = epub.read_epub(str(filepath))

    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else Path(filepath).stem

    author = book.get_metadata("DC", "creator")
    author = author[0][0] if author else "Unknown"

    chapters: list[Chapter] = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        paras = _html_to_paragraphs(item.get_content())
        if not paras:
            continue
        chapters.append(Chapter(title=item.get_name(), paragraphs=paras))

    return ParsedBook(title=title, author=author, chapters=chapters)
