"""
Settings screen — font size and upload server toggle.

Navigation:
  ↑↓       move between settings
  ←→ / ↵   cycle / toggle value
  BACK     return to library
"""
from __future__ import annotations
import socket
from PIL import Image

from core import fonts
from core.state_machine import Screen, StateMachine
from core import server_manager
from hal.input_base import ButtonEvent, Button
from data.database import get_setting, set_setting

FONT_SIZES = [18, 20, 22, 24, 26, 28]
MARGIN_X = 24
ITEM_H = 72


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
    _ITEMS = ["Font Size", "Upload Server"]

    def __init__(self, sm: StateMachine):
        super().__init__(sm)
        self._cursor = 0
        self._font_idx = 2          # default index → 22
        self._server_on = False

    def on_enter(self) -> None:
        fs = int(get_setting("font_size", "22"))
        self._font_idx = FONT_SIZES.index(fs) if fs in FONT_SIZES else 2
        self._server_on = server_manager.is_running()
        self.sm.mark_dirty()

    def render(self) -> Image.Image:
        img, draw = self.blank_canvas()
        header = fonts.load(20, bold=True)
        label_f = fonts.load(17)
        value_f = fonts.load(17, bold=True)
        hint_f  = fonts.load(13)

        # Header
        draw.text((MARGIN_X, 20), "Settings", font=header, fill="black")
        draw.line([(MARGIN_X, 52), (self.WIDTH - MARGIN_X, 52)], fill=(180, 180, 180), width=1)

        items = [
            ("Font Size", f"{FONT_SIZES[self._font_idx]} px"),
            ("Upload Server", "ON" if self._server_on else "OFF"),
        ]

        for i, (label, value) in enumerate(items):
            y = 68 + i * ITEM_H
            selected = i == self._cursor

            if selected:
                draw.rounded_rectangle(
                    [(MARGIN_X - 8, y - 8), (self.WIDTH - MARGIN_X + 8, y + ITEM_H - 16)],
                    radius=10, fill=(240, 240, 240),
                )

            draw.text((MARGIN_X, y), label, font=label_f, fill="black")

            # Value pill
            vw = value_f.getbbox(value)[2] - value_f.getbbox(value)[0]
            pill_x = self.WIDTH - MARGIN_X - vw - 20
            pill_color = (30, 30, 30) if (i == 1 and self._server_on) else (100, 100, 100)
            draw.rounded_rectangle(
                [(pill_x - 8, y - 2), (self.WIDTH - MARGIN_X, y + 26)],
                radius=8, fill=pill_color,
            )
            draw.text((pill_x, y), value, font=value_f, fill="white")

        # URL when server is running
        if self._server_on:
            url_y = 68 + len(items) * ITEM_H + 10
            url_f = fonts.load(15)
            draw.text((MARGIN_X, url_y), "Connect from your browser:", font=hint_f, fill=(100, 100, 100))
            draw.text((MARGIN_X, url_y + 20), f"http://{_local_ip()}:{server_manager.PORT}", font=url_f, fill=(0, 80, 180))

        # Bottom hint
        draw.text(
            (MARGIN_X, self.HEIGHT - 30),
            "↑↓ navigate   ←→/↵ change   ESC back",
            font=hint_f, fill=(160, 160, 160),
        )
        return img

    def handle(self, event: ButtonEvent) -> None:
        if not event.pressed:
            return
        if event.button == Button.UP:
            self._cursor = max(0, self._cursor - 1)
            self.sm.mark_dirty()
        elif event.button == Button.DOWN:
            self._cursor = min(len(self._ITEMS) - 1, self._cursor + 1)
            self.sm.mark_dirty()
        elif event.button in (Button.LEFT, Button.RIGHT, Button.SELECT):
            self._change()
        elif event.button == Button.BACK:
            from screens.library import LibraryScreen
            self.sm.switch(LibraryScreen(self.sm))

    def _change(self) -> None:
        if self._cursor == 0:
            self._font_idx = (self._font_idx + 1) % len(FONT_SIZES)
            set_setting("font_size", str(FONT_SIZES[self._font_idx]))
        elif self._cursor == 1:
            if self._server_on:
                server_manager.stop()
            else:
                server_manager.start()
            self._server_on = server_manager.is_running()
        self.sm.mark_dirty()
