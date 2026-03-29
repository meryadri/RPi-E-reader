"""
Upload info screen — shows the Flask server URL so the user knows where to upload books.
"""
from __future__ import annotations
from PIL import ImageFont
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
        font = ImageFont.load_default()
        ip = _local_ip()

        draw.text((40, 40), "Upload Books", font=font, fill="black")
        draw.line([(40, 70), (self.WIDTH - 40, 70)], fill="black", width=1)
        draw.text((40, 100), "Open the following address in your browser:", font=font, fill="black")
        draw.text((40, 140), f"http://{ip}:3003", font=font, fill=(0, 80, 180))
        draw.text((40, 200), "Select an EPUB file and click Upload.", font=font, fill=(80, 80, 80))
        draw.text((40, self.HEIGHT - 40), "Press BACK to return to Library", font=font, fill=(120, 120, 120))
        return img

    def handle(self, event: ButtonEvent) -> None:
        if event.pressed and event.button == Button.BACK:
            from screens.library import LibraryScreen
            self.sm.switch(LibraryScreen(self.sm))
