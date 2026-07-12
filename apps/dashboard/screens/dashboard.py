"""
Dashboard screen — landscape (800×480), no buttons.

Layout
------
+-------------------------------------------------------------+
| 14:32                                   [sun]  24°C         |
| Sunday 12 July                                 Clear        |
|-------------------------------------------------------------|
| CALENDAR                    |  TRAINING                     |
| 09:00  Standup              |  Today: Tempo run             |
| 13:00  Lunch w/ Alex        |  8 km @ 4:45/km               |
| 18:30  Gym                  |  Wk 3 / 12                    |
|                             |  32 km this week              |
+-------------------------------------------------------------+

The clock redraws itself once a minute via poll().
"""
from __future__ import annotations
import math

from PIL import Image

from display import fonts
from display.runtime import Screen
from apps.dashboard import data

MARGIN = 28
TOP_H = 150          # height of the top clock/weather band


class DashboardScreen(Screen):
    def __init__(self, sm):
        super().__init__(sm)
        self._last_minute: str | None = None

    def on_enter(self) -> None:
        self.sm.mark_dirty("full")

    # No buttons on this device.
    def handle(self, event) -> None:  # noqa: D401
        pass

    def poll(self) -> None:
        """Redraw when the displayed minute changes (clock tick)."""
        now = data.get_now().strftime("%H:%M")
        if now != self._last_minute:
            self.sm.mark_dirty("full")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> Image.Image:
        img, draw = self.blank_canvas()

        now = data.get_now()
        self._last_minute = now.strftime("%H:%M")

        self._draw_top(draw, now, data.get_weather())
        # Divider under the top band
        draw.line([(MARGIN, TOP_H), (self.WIDTH - MARGIN, TOP_H)], fill="black", width=2)
        # Vertical divider between the two bottom columns
        mid_x = self.WIDTH // 2
        draw.line([(mid_x, TOP_H + 16), (mid_x, self.HEIGHT - MARGIN)], fill="black", width=1)

        self._draw_calendar(draw, data.get_events(), x0=MARGIN, x1=mid_x - 20)
        self._draw_training(draw, data.get_training(), x0=mid_x + 24)

        return img

    def _draw_top(self, draw, now, weather) -> None:
        f_clock = fonts.load(96, bold=True)
        f_date = fonts.load(26)

        draw.text((MARGIN, 18), now.strftime("%H:%M"), font=f_clock, fill="black")
        date_str = now.strftime("%A %-d %B") if hasattr(now, "strftime") else ""
        draw.text((MARGIN + 4, 122), date_str, font=f_date, fill="black")

        # Weather block, right-aligned
        f_temp = fonts.load(52, bold=True)
        f_cond = fonts.load(24)
        temp_str = f"{weather['temp_c']}°C"
        cond_str = weather["condition"]

        temp_w = _text_w(draw, temp_str, f_temp)
        temp_x = self.WIDTH - MARGIN - temp_w
        draw.text((temp_x, 40), temp_str, font=f_temp, fill="black")

        cond_w = _text_w(draw, cond_str, f_cond)
        draw.text((self.WIDTH - MARGIN - cond_w, 100), cond_str, font=f_cond, fill="black")

        # Simple drawn sun icon to the left of the temperature (glyph-independent)
        self._draw_sun(draw, cx=temp_x - 52, cy=66, r=22)

    def _draw_calendar(self, draw, events, x0, x1) -> None:
        f_head = fonts.load(22, bold=True)
        f_time = fonts.load(22, bold=True)
        f_item = fonts.load(22)

        y = TOP_H + 26
        draw.text((x0, y), "CALENDAR", font=f_head, fill="black")
        y += 44
        if not events:
            draw.text((x0, y), "No events today", font=f_item, fill="black")
            return
        for ev in events:
            draw.text((x0, y), ev["time"], font=f_time, fill="black")
            draw.text((x0 + 92, y), ev["title"], font=f_item, fill="black")
            y += 42

    def _draw_training(self, draw, tr, x0) -> None:
        f_head = fonts.load(22, bold=True)
        f_big = fonts.load(30, bold=True)
        f_item = fonts.load(22)
        f_meta = fonts.load(20)

        y = TOP_H + 26
        draw.text((x0, y), "TRAINING", font=f_head, fill="black")
        y += 46
        draw.text((x0, y), tr["today"], font=f_big, fill="black")
        y += 44
        draw.text((x0, y), tr["detail"], font=f_item, fill="black")
        y += 46
        draw.text((x0, y), tr["week"], font=f_meta, fill="black")
        y += 30
        draw.text((x0, y), tr["volume"], font=f_meta, fill="black")

    @staticmethod
    def _draw_sun(draw, cx, cy, r) -> None:
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline="black", width=3)
        for i in range(8):
            a = math.pi * i / 4
            x1 = cx + math.cos(a) * (r + 5)
            y1 = cy + math.sin(a) * (r + 5)
            x2 = cx + math.cos(a) * (r + 13)
            y2 = cy + math.sin(a) * (r + 13)
            draw.line([(x1, y1), (x2, y2)], fill="black", width=3)


def _text_w(draw, text, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]
