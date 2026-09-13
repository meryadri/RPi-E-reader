"""
Dashboard screen — landscape (800×480), no buttons.

Layout
------
+-------------------------------------------------------------+
| 14:32                                   [sun]  24°C         |
| Sunday 12 July                                 Clear        |
|-------------------------------------------------------------|
| ALL-DAY                     |  TRAINING                     |
| • Dentist                   |  Today: Tempo run             |
| 2/5 Berlin trip             |  8 km @ 4:45/km               |
| • Anna's birthday           |  Wk 3 / 12                    |
|                             |  32 km this week              |
+-------------------------------------------------------------+

The clock redraws itself once a minute; the calendar column redraws only when
the event list actually changes.  Both use a partial (flicker-free) refresh.
"""
from __future__ import annotations
import math

from PIL import Image

from display import fonts
from display.runtime import Screen
from apps.dashboard import data
from integrations import google_calendar as gcal

MARGIN = 28
TOP_H = 150          # height of the top clock/weather band

ROW_H = 42
ROW_Y0 = TOP_H + 70  # first event row
MARKER_W = 38        # left gutter: bullet, or "2/5" for a multi-day event


class DashboardScreen(Screen):
    def __init__(self, sm):
        super().__init__(sm)
        self._last_minute: str | None = None
        self._cal_version: int | None = None

    def on_enter(self) -> None:
        self.sm.mark_dirty("full")

    # No buttons on this device.
    def handle(self, event) -> None:  # noqa: D401
        pass

    def poll(self) -> None:
        """Redraw when the clock ticks or the calendar changes — nothing else."""
        if self._last_minute is None or self._cal_version is None:
            # First frame: on_enter already queued a "full" refresh to clear the
            # panel.  Marking dirty here would downgrade it to "partial" and
            # leave whatever was on the e-ink before showing through.
            return

        now = data.get_now().strftime("%H:%M")
        if now != self._last_minute:
            # "partial" is flicker-free.  display/hal/rpi.py already forces a
            # full refresh every FULL_REFRESH_INTERVAL partials to clear
            # ghosting, so this keeps the anti-ghosting behaviour without
            # flashing the whole panel every 60 seconds.
            self.sm.mark_dirty("partial")
            return
        if data.get_calendar().version != self._cal_version:
            self.sm.mark_dirty("partial")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> Image.Image:
        img, draw = self.blank_canvas()

        now = data.get_now()
        self._last_minute = now.strftime("%H:%M")

        # Read the calendar snapshot exactly once and use that object
        # throughout.  Reading it twice could straddle a publish from the
        # refresh thread and render an inconsistent frame.
        cal = data.get_calendar()
        # Record the version from the snapshot actually drawn, not the one seen
        # in poll() — if the worker published in between, storing poll()'s
        # version would mark the screen dirty again for content already shown.
        self._cal_version = cal.version

        self._draw_top(draw, now, data.get_weather())
        # Divider under the top band
        draw.line([(MARGIN, TOP_H), (self.WIDTH - MARGIN, TOP_H)], fill="black", width=2)
        # Vertical divider between the two bottom columns
        mid_x = self.WIDTH // 2
        draw.line([(mid_x, TOP_H + 16), (mid_x, self.HEIGHT - MARGIN)], fill="black", width=1)

        self._draw_calendar(draw, cal, x0=MARGIN, x1=mid_x - 20)
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

    def _draw_calendar(self, draw, cal, x0, x1) -> None:
        f_head = fonts.load(22, bold=True)
        f_item = fonts.load(22)
        f_small = fonts.load(16)
        f_note = fonts.load(18)

        y = TOP_H + 26
        draw.text((x0, y), "ALL-DAY", font=f_head, fill="black")

        # Freshness marker, right-aligned on the header line.  Staleness is
        # derived from the snapshot's age, so it also catches a refresh thread
        # that died or hung rather than only a clean failure.
        if cal.status == gcal.OK and cal.is_stale():
            note = f"as of {cal.fetched_at_label()}" if cal.fetched_at else "stale"
            draw.text((x1 - _text_w(draw, note, f_small), y + 6),
                      note, font=f_small, fill="black")
        elif cal.partial:
            note = "partial"
            draw.text((x1 - _text_w(draw, note, f_small), y + 6),
                      note, font=f_small, fill="black")

        y = ROW_Y0

        # Guard against a snapshot for a different day ever reaching the screen:
        # yesterday's all-day events shown as today's is worse than showing none.
        events = cal.events if cal.day == gcal.today() else ()

        if not events:
            draw.text((x0, y), _empty_text(cal), font=f_item, fill="black")
            if cal.status == gcal.AUTH_REQUIRED:
                draw.text((x0, y + 30),
                          "python -m integrations.google_calendar",
                          font=f_small, fill="black")
            return

        # Derive the cap from the geometry so it survives a layout edit.
        y_limit = self.HEIGHT - MARGIN - ROW_H
        max_rows = max(1, (y_limit - ROW_Y0) // ROW_H + 1)

        shown = events
        overflow = 0
        if len(events) > max_rows:
            shown = events[: max_rows - 1]
            overflow = len(events) - len(shown)

        title_x = x0 + MARKER_W
        title_w = x1 - title_x

        for ev in shown:
            if ev["days_total"] > 1:
                marker = f"{ev['day_index'] + 1}/{ev['days_total']}"
                draw.text((x0, y + 5), marker, font=f_small, fill="black")
            else:
                # Drawn rather than a "•" glyph: CommitMono renders U+2022 as a
                # low period, and a font without it would show a tofu box.
                cx, cy, r = x0 + 7, y + 14, 3
                draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill="black")

            title = ev.get("title") or "(no title)"
            draw.text((title_x, y), _ellipsize(draw, title, f_item, title_w),
                      font=f_item, fill="black")
            y += ROW_H

        if overflow:
            draw.text((title_x, y + 2), f"+{overflow} more", font=f_note, fill="black")

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


def _empty_text(cal) -> str:
    if cal.status == gcal.AUTH_REQUIRED:
        return "Calendar not connected"
    if cal.status == gcal.LOADING:
        return "Checking calendar..."
    if cal.status == gcal.ERROR:
        return "Calendar unavailable"
    return "No all-day events"


def _text_w(draw, text, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _ellipsize(draw, text, font, max_w) -> str:
    """Trim `text` so it fits `max_w`, appending an ellipsis.

    Uses "..." rather than the single-character U+2026: if the bundled font
    lacks that glyph you get a visible tofu box instead.
    """
    if _text_w(draw, text, font) <= max_w:
        return text
    ell = "..."
    while text and _text_w(draw, text + ell, font) > max_w:
        text = text[:-1]
    return (text.rstrip() + ell) if text else ell
