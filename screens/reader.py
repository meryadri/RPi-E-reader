"""
Reader screen — renders book pages and handles navigation.
"""
from __future__ import annotations
from PIL import ImageFont
from core.state_machine import Screen, StateMachine
from core.epub_parser import parse_epub
from core.paginator import paginate
from core.renderer import render_page
from hal.input_base import ButtonEvent, Button
from data.database import Book, update_progress


class ReaderScreen(Screen):
    def __init__(self, sm: StateMachine, book: Book):
        super().__init__(sm)
        self._book = book
        self._pages = []
        self._current = book.current_page

    def on_enter(self) -> None:
        parsed = parse_epub(self._book.filepath)
        self._pages = paginate(parsed.full_text_paragraphs)
        total = len(self._pages)
        # Clamp saved position
        self._current = min(self._book.current_page, max(0, total - 1))
        update_progress(self._book.id, self._current, total)
        self.sm.mark_dirty()

    def render(self):
        if not self._pages:
            img, draw = self.blank_canvas()
            draw.text((40, 40), "Could not render book.", fill="black")
            return img
        page = self._pages[self._current]
        return render_page(page, len(self._pages), self._book.title)

    def handle(self, event: ButtonEvent) -> None:
        if not event.pressed:
            return
        if event.button in (Button.RIGHT, Button.DOWN, Button.SELECT):
            self._go(1)
        elif event.button in (Button.LEFT, Button.UP):
            self._go(-1)
        elif event.button == Button.BACK:
            from screens.library import LibraryScreen
            self.sm.switch(LibraryScreen(self.sm))

    def _go(self, delta: int) -> None:
        new = self._current + delta
        if 0 <= new < len(self._pages):
            self._current = new
            update_progress(self._book.id, self._current, len(self._pages))
            self.sm.mark_dirty()
