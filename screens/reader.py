"""
Reader screen — renders book pages and handles navigation.
Font size and font name are read from the settings database on every open.
"""
from __future__ import annotations
from core.state_machine import Screen, StateMachine
from core.epub_parser import parse_epub
from core.paginator import paginate, DEFAULT_FONT_SIZE
from core.renderer import render_page
from core import fonts
from hal.input_base import ButtonEvent, Button
from data.database import Book, update_progress, get_setting


class ReaderScreen(Screen):
    def __init__(self, sm: StateMachine, book: Book):
        super().__init__(sm)
        self._book = book
        self._pages = []
        self._current = book.current_page
        self._font_size = DEFAULT_FONT_SIZE
        self._font_name = fonts.COMMIT_MONO

    def on_enter(self) -> None:
        self._font_size = int(get_setting("font_size", str(DEFAULT_FONT_SIZE)))
        self._font_name = get_setting("font_name", fonts.COMMIT_MONO)
        parsed = parse_epub(self._book.filepath)
        self._pages = paginate(
            parsed.full_text_paragraphs,
            font_size=self._font_size,
            font_name=self._font_name,
        )
        total = len(self._pages)
        self._current = min(self._book.current_page, max(0, total - 1))
        update_progress(self._book.id, self._current, total)
        self.sm.mark_dirty()

    def render(self):
        if not self._pages:
            img, draw = self.blank_canvas()
            draw.text((40, 40), "Could not render book.",
                      font=fonts.load(18), fill="black")
            return img
        page = self._pages[self._current]
        return render_page(
            page,
            len(self._pages),
            self._book.title,
            font_size=self._font_size,
            font_name=self._font_name,
        )

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
