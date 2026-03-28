"""
Library screen — shows all books in the database.
Navigate with UP/DOWN, open with SELECT.
"""
from __future__ import annotations
from PIL import ImageFont
from core.state_machine import Screen, StateMachine
from hal.input_base import ButtonEvent, Button
from data.database import get_all_books, Book


TITLE_FONT_SIZE = 22
ITEM_FONT_SIZE = 18
ITEM_HEIGHT = 44
VISIBLE_ITEMS = 9
MARGIN_X = 40
MARGIN_TOP = 60


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

    def render(self):
        img, draw = self.blank_canvas()
        font_title = ImageFont.load_default()
        font_item = ImageFont.load_default()

        draw.text((MARGIN_X, 18), "Library", font=font_title, fill="black")
        draw.line([(MARGIN_X, 50), (self.WIDTH - MARGIN_X, 50)], fill="black", width=1)

        if not self._books:
            draw.text((MARGIN_X, MARGIN_TOP + 20), "No books yet.  Upload an EPUB via the web interface.", font=font_item, fill=(120, 120, 120))
            return img

        visible = self._books[self._scroll: self._scroll + VISIBLE_ITEMS]
        for i, book in enumerate(visible):
            y = MARGIN_TOP + i * ITEM_HEIGHT
            abs_idx = self._scroll + i
            selected = abs_idx == self._cursor

            if selected:
                draw.rectangle([(MARGIN_X - 8, y - 4), (self.WIDTH - MARGIN_X + 8, y + ITEM_HEIGHT - 8)], fill=(220, 220, 220))

            draw.text((MARGIN_X, y), book.title, font=font_item, fill="black")
            draw.text((MARGIN_X, y + 22), f"{book.author}  —  p.{book.current_page}/{book.total_pages}", font=font_item, fill=(100, 100, 100))

        # Scroll indicator
        if len(self._books) > VISIBLE_ITEMS:
            pct = self._cursor / max(1, len(self._books) - 1)
            bar_h = self.HEIGHT - MARGIN_TOP - 20
            dot_y = MARGIN_TOP + int(pct * bar_h)
            draw.rectangle([(self.WIDTH - 16, MARGIN_TOP), (self.WIDTH - 10, self.HEIGHT - 20)], fill=(200, 200, 200))
            draw.rectangle([(self.WIDTH - 16, dot_y - 8), (self.WIDTH - 10, dot_y + 8)], fill=(80, 80, 80))

        return img

    def handle(self, event: ButtonEvent) -> None:
        if not event.pressed:
            return
        if event.button == Button.DOWN:
            if self._cursor < len(self._books) - 1:
                self._cursor += 1
                if self._cursor >= self._scroll + VISIBLE_ITEMS:
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
                self._open_book(self._books[self._cursor])

    def _open_book(self, book: Book) -> None:
        from screens.reader import ReaderScreen
        reader = ReaderScreen(self.sm, book)
        self.sm.switch(reader)
