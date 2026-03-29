"""
Settings screen.

Items:
  Font          CommitMono ↔ System Sans   (←→ or ↵ to cycle)
  Font Size     8 – 32 px                  (← to decrease, → to increase)
  Upload Server OFF ↔ ON                   (←→ or ↵ to toggle)

Navigation:
  ↑↓    move between items
  ←→    change value (decrease / increase for size; cycle for others)
  ↵     same as →
  ESC   save and return to library
"""
from __future__ import annotations
import socket
from PIL import Image

from core import fonts
from core.state_machine import Screen, StateMachine
from core import server_manager
from core.paginator import FONT_SIZE_MIN, FONT_SIZE_MAX, DEFAULT_FONT_SIZE
from hal.input_base import ButtonEvent, Button
from data.database import get_setting, set_setting

MARGIN_X = 24
ITEM_H   = 80

_FONT_OPTIONS = [fonts.COMMIT_MONO, fonts.SYSTEM]
_FONT_LABELS  = {fonts.COMMIT_MONO: "CommitMono", fonts.SYSTEM: "System Sans"}

_ITEMS = ["Font", "Font Size", "Upload Server"]

QUOTE = "Quidquid latine dictum sit, altum videtur."


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class SettingsScreen(Screen):

    def __init__(self, sm: StateMachine):
        super().__init__(sm)
        self._cursor    = 0
        self._font_name = fonts.COMMIT_MONO
        self._font_size = DEFAULT_FONT_SIZE
        self._server_on = False

    def on_enter(self) -> None:
        self._font_name = get_setting("font_name", fonts.COMMIT_MONO)
        self._font_size = int(get_setting("font_size", str(DEFAULT_FONT_SIZE)))
        self._server_on = server_manager.is_running()
        self.sm.mark_dirty()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self) -> Image.Image:
        img, draw = self.blank_canvas()
        f_header = fonts.load(20, bold=True)
        f_label  = fonts.load(17)
        f_value  = fonts.load(17, bold=True)
        f_hint   = fonts.load(13)

        # Header
        draw.text((MARGIN_X, 20), "Settings", font=f_header, fill="black")
        draw.line([(MARGIN_X, 52), (self.WIDTH - MARGIN_X, 52)],
                  fill=(180, 180, 180), width=1)

        values = [
            _FONT_LABELS[self._font_name],
            f"{self._font_size} px",
            "ON" if self._server_on else "OFF",
        ]

        for i, (label, value) in enumerate(zip(_ITEMS, values)):
            y       = 64 + i * ITEM_H
            sel     = i == self._cursor

            if sel:
                draw.rounded_rectangle(
                    [(MARGIN_X - 8, y - 6),
                     (self.WIDTH - MARGIN_X + 8, y + ITEM_H - 14)],
                    radius=10, fill=(240, 240, 240),
                )

            draw.text((MARGIN_X, y + 4), label, font=f_label, fill="black")

            if i == 1 and sel:
                # Font Size selected → show  −  16 px  +
                self._draw_stepper(draw, f_value, f_hint, y)
            else:
                # Normal pill
                pill_color = (30, 30, 30) if (i == 2 and self._server_on) else (100, 100, 100)
                vw = f_value.getbbox(value)[2] - f_value.getbbox(value)[0]
                pill_x = self.WIDTH - MARGIN_X - vw - 20
                draw.rounded_rectangle(
                    [(pill_x - 8, y), (self.WIDTH - MARGIN_X, y + 28)],
                    radius=8, fill=pill_color,
                )
                draw.text((pill_x, y + 2), value, font=f_value, fill="white")

        # Font preview box
        preview_y = 64 + len(_ITEMS) * ITEM_H + 12
        preview_bottom = self._draw_preview(img, draw, preview_y)

        # URL when server is running — placed below the preview
        if self._server_on:
            url_y = preview_bottom + 14
            draw.text((MARGIN_X, url_y),
                      "Open in your browser:", font=f_hint, fill=(120, 120, 120))
            draw.text((MARGIN_X, url_y + 20),
                      f"http://{_local_ip()}:{server_manager.PORT}",
                      font=fonts.load(15), fill=(0, 80, 180))

        # Bottom hint — changes when font size row is active
        if self._cursor == 1:
            hint = "← smaller   → larger   ↑↓ navigate   ESC back"
        else:
            hint = "←→/↵ change   ↑↓ navigate   ESC back"
        draw.text((MARGIN_X, self.HEIGHT - 28), hint, font=f_hint, fill=(170, 170, 170))

        return img

    def _draw_preview(self, img, draw, y_start: int) -> None:
        """Render the quote in the currently selected font and size."""
        from PIL import Image as _Img
        f_label   = fonts.load(11)
        f_preview = fonts.load(self._font_size, font_name=self._font_name)

        pad    = 14
        box_x  = MARGIN_X
        box_w  = self.WIDTH - 2 * MARGIN_X
        max_tw = box_w - 2 * pad

        # Word-wrap the quote
        words, lines, current = QUOTE.split(), [], ""
        for word in words:
            candidate = (current + " " + word).strip()
            if f_preview.getbbox(candidate)[2] <= max_tw:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        bh      = f_preview.getbbox("Ag")
        lh      = (bh[3] - bh[1]) + 5
        label_h = 18
        box_h   = label_h + len(lines) * lh + 2 * pad

        draw.rounded_rectangle(
            [(box_x, y_start), (box_x + box_w, y_start + box_h)],
            radius=10, fill=(248, 248, 248),
        )
        draw.rounded_rectangle(
            [(box_x, y_start), (box_x + box_w, y_start + box_h)],
            radius=10, outline=(210, 210, 210), width=1,
        )

        draw.text((box_x + pad, y_start + 6), "Preview", font=f_label, fill=(180, 180, 180))

        y = y_start + label_h + pad
        for line in lines:
            draw.text((box_x + pad, y), line, font=f_preview, fill=(40, 40, 40))
            y += lh

        return y_start + box_h  # bottom edge

    def _draw_stepper(self, draw, f_value, f_hint, y: int) -> None:
        """Render  −  16 px  +  for the font-size row."""
        at_min = self._font_size <= FONT_SIZE_MIN
        at_max = self._font_size >= FONT_SIZE_MAX

        minus_col = (200, 200, 200) if at_min else (60, 60, 60)
        plus_col  = (200, 200, 200) if at_max else (60, 60, 60)

        size_str = f"{self._font_size} px"
        sw = f_value.getbbox(size_str)[2] - f_value.getbbox(size_str)[0]

        right_edge = self.WIDTH - MARGIN_X
        plus_x     = right_edge - f_hint.getbbox("+")[2] - 4
        size_x     = plus_x - sw - 14
        minus_x    = size_x - f_hint.getbbox("−")[2] - 14

        draw.text((minus_x, y + 2), "−", font=fonts.load(20, bold=True), fill=minus_col)
        draw.text((size_x,  y + 2), size_str, font=f_value, fill="black")
        draw.text((plus_x,  y + 2), "+", font=fonts.load(20, bold=True), fill=plus_col)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle(self, event: ButtonEvent) -> None:
        if not event.pressed:
            return
        if event.button == Button.UP:
            self._cursor = max(0, self._cursor - 1)
            self.sm.mark_dirty()
        elif event.button == Button.DOWN:
            self._cursor = min(len(_ITEMS) - 1, self._cursor + 1)
            self.sm.mark_dirty()
        elif event.button == Button.LEFT:
            self._change(-1)
        elif event.button in (Button.RIGHT, Button.SELECT):
            self._change(+1)
        elif event.button == Button.BACK:
            from screens.library import LibraryScreen
            self.sm.switch(LibraryScreen(self.sm))

    def _change(self, direction: int) -> None:
        if self._cursor == 0:                          # Font
            idx = _FONT_OPTIONS.index(self._font_name)
            self._font_name = _FONT_OPTIONS[(idx + direction) % len(_FONT_OPTIONS)]
            set_setting("font_name", self._font_name)

        elif self._cursor == 1:                        # Font Size
            new = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, self._font_size + direction))
            if new != self._font_size:
                self._font_size = new
                set_setting("font_size", str(self._font_size))

        elif self._cursor == 2:                        # Upload Server
            if self._server_on:
                server_manager.stop()
            else:
                server_manager.start()
            self._server_on = server_manager.is_running()

        self.sm.mark_dirty()
