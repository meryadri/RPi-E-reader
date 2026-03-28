"""
Library screen — scrollable book list with cover thumbnails.

Navigation:
  ↑↓      navigate
  ↵       open selected book
  M       open settings
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image as PILImage

from core import fonts
from core.state_machine import Screen, StateMachine
from hal.input_base import ButtonEvent, Button
from data.database import get_all_books, Book

MARGIN_X  = 18
HEADER_H  = 56      # px reserved for title + separator
ITEM_H    = 104     # px per book row
THUMB_W   = 62
THUMB_H   = 86
TEXT_X    = MARGIN_X + THUMB_W + 12
HINT_H    = 30      # bottom hint bar
VISIBLE   = 6       # items shown at once (6 × 104 = 624, fits in 800-56-30=714)


def _truncate(text: str, font, max_w: int) -> str:
    if not text:
        return ""
    bbox = font.getbbox(text)
    if bbox[2] - bbox[0] <= max_w:
        return text
    while text:
        candidate = text + "…"
        b = font.getbbox(candidate)
        if b[2] - b[0] <= max_w:
            return candidate
        text = text[:-1]
    return "…"


def _load_thumb(cover_path: str) -> PILImage.Image | None:
    try:
        if cover_path and Path(cover_path).exists():
            img = PILImage.open(cover_path).convert("RGB")
            img = img.resize((THUMB_W, THUMB_H), PILImage.LANCZOS)
            return img
    except Exception:
        pass
    return None


class LibraryScreen(Screen):
    def __init__(self, sm: StateMachine):
        super().__init__(sm)
        self._books: list[Book] = []
        self._cursor = 0
        self._scroll = 0

    def on_enter(self) -> None:
        self._books = get_all_books()
        self._cursor = min(self._cursor, max(0, len(self._books) - 1))
        self.sm.mark_dirty()

    def render(self) -> PILImage.Image:
        img, draw = self.blank_canvas()

        f_header  = fonts.load(20, bold=True)
        f_title   = fonts.load(17, bold=True)
        f_author  = fonts.load(14)
        f_meta    = fonts.load(13, italic=True)
        f_hint    = fonts.load(12)

        # Header
        draw.text((MARGIN_X, 16), "Library", font=f_header, fill="black")
        draw.line(
            [(MARGIN_X, HEADER_H - 6), (self.WIDTH - MARGIN_X, HEADER_H - 6)],
            fill=(200, 200, 200), width=1,
        )

        if not self._books:
            draw.text(
                (MARGIN_X, HEADER_H + 24),
                "No books yet.  Upload via the web interface.",
                font=f_author, fill=(150, 150, 150),
            )
        else:
            text_max_w = self.WIDTH - TEXT_X - MARGIN_X - 14  # leave room for scroll bar

            visible_books = self._books[self._scroll: self._scroll + VISIBLE]
            for i, book in enumerate(visible_books):
                abs_idx = self._scroll + i
                y = HEADER_H + i * ITEM_H
                selected = abs_idx == self._cursor

                # Row highlight
                if selected:
                    draw.rounded_rectangle(
                        [(MARGIN_X - 6, y + 4), (self.WIDTH - MARGIN_X + 6, y + ITEM_H - 4)],
                        radius=10, fill=(240, 240, 240),
                    )

                # Cover thumbnail
                thumb = _load_thumb(book.cover_path)
                thumb_x, thumb_y = MARGIN_X, y + (ITEM_H - THUMB_H) // 2
                if thumb:
                    img.paste(thumb, (thumb_x, thumb_y))
                    if selected:
                        draw.rectangle(
                            [(thumb_x, thumb_y), (thumb_x + THUMB_W, thumb_y + THUMB_H)],
                            outline=(180, 180, 180), width=1,
                        )
                else:
                    draw.rounded_rectangle(
                        [(thumb_x, thumb_y), (thumb_x + THUMB_W, thumb_y + THUMB_H)],
                        radius=4, fill=(220, 220, 220),
                    )
                    initial = (book.title[0].upper()) if book.title else "?"
                    draw.text(
                        (thumb_x + THUMB_W // 2 - 8, thumb_y + THUMB_H // 2 - 14),
                        initial, font=fonts.load(22, bold=True), fill=(160, 160, 160),
                    )

                # Text block
                tx, ty = TEXT_X, y + 14
                title_str  = _truncate(book.title, f_title, text_max_w)
                author_str = _truncate(book.author, f_author, text_max_w)

                draw.text((tx, ty),      title_str,  font=f_title,  fill="black")
                draw.text((tx, ty + 24), author_str, font=f_author, fill=(90, 90, 90))

                meta_parts = []
                if book.year:
                    meta_parts.append(book.year)
                if book.total_pages:
                    pct = int(book.current_page / book.total_pages * 100)
                    meta_parts.append(f"p.{book.current_page}/{book.total_pages}  ({pct}%)")
                if meta_parts:
                    draw.text((tx, ty + 46), "  ·  ".join(meta_parts), font=f_meta, fill=(140, 140, 140))

            # Scroll bar (right edge)
            if len(self._books) > VISIBLE:
                bar_x = self.WIDTH - MARGIN_X + 2
                bar_top = HEADER_H + 8
                bar_bot = HEADER_H + VISIBLE * ITEM_H - 8
                bar_h = bar_bot - bar_top
                draw.rounded_rectangle(
                    [(bar_x, bar_top), (bar_x + 4, bar_bot)],
                    radius=2, fill=(220, 220, 220),
                )
                handle_frac = VISIBLE / len(self._books)
                handle_h = max(20, int(bar_h * handle_frac))
                handle_top = bar_top + int((self._scroll / len(self._books)) * bar_h)
                draw.rounded_rectangle(
                    [(bar_x, handle_top), (bar_x + 4, handle_top + handle_h)],
                    radius=2, fill=(100, 100, 100),
                )

        # Bottom hint
        draw.line(
            [(MARGIN_X, self.HEIGHT - HINT_H - 2), (self.WIDTH - MARGIN_X, self.HEIGHT - HINT_H - 2)],
            fill=(220, 220, 220), width=1,
        )
        draw.text(
            (MARGIN_X, self.HEIGHT - HINT_H + 4),
            "↑↓ navigate   ↵ open   M settings",
            font=f_hint, fill=(170, 170, 170),
        )

        return img

    def handle(self, event: ButtonEvent) -> None:
        if not event.pressed:
            return
        if event.button == Button.DOWN:
            if self._cursor < len(self._books) - 1:
                self._cursor += 1
                if self._cursor >= self._scroll + VISIBLE:
                    self._scroll += 1
                self.sm.mark_dirty()
        elif event.button == Button.UP:
            if self._cursor > 0:
                self._cursor -= 1
                if self._cursor < self._scroll:
                    self._scroll -= 1
                self.sm.mark_dirty()
        elif event.button == Button.SELECT:
            if self._books:
                from screens.reader import ReaderScreen
                self.sm.switch(ReaderScreen(self.sm, self._books[self._cursor]))
        elif event.button == Button.MENU:
            from screens.settings import SettingsScreen
            self.sm.switch(SettingsScreen(self.sm))
