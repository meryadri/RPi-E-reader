"""
Upload info screen — shows the Flask server URL so the user knows where to upload books.
"""
from __future__ import annotations
from core import fonts
from core.state_machine import Screen, StateMachine
from hal.input_base import ButtonEvent, Button
import socket


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class UploadInfoScreen(Screen):
    def render(self):
        img, draw = self.blank_canvas()
        ip = _local_ip()

        f_title = fonts.load(24, bold=True)
        f_body  = fonts.load(18)
        f_url   = fonts.load(20, bold=True)
        f_hint  = fonts.load(16)

        draw.text((16, 40), "Upload Books", font=f_title, fill="black")
        draw.line([(16, 76), (self.WIDTH - 16, 76)], fill="black", width=1)
        draw.text((16, 100), "Open in your browser:", font=f_body, fill="black")
        draw.text((16, 140), f"http://{ip}:3003", font=f_url, fill="black")
        draw.text((16, 200), "Select an EPUB file and click Upload.", font=f_body, fill="black")
        draw.text((16, self.HEIGHT - 40), "Press BACK to return to Library", font=f_hint, fill="black")
        return img

    def handle(self, event: ButtonEvent) -> None:
        if event.pressed and event.button == Button.BACK:
            from screens.library import LibraryScreen
            self.sm.switch(LibraryScreen(self.sm))
