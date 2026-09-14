"""
Dashboard screen — landscape (800×480), no buttons.

Layout
------
+---------------------------------------------------------------+
| 14:32                      [icon]  18°C / 64°F                |
| Sunday, September 13            Partly cloudy · 12 km/h       |
|---------------------------------------------------------------|
| .-------------------------.  |  TODAY                    3/8  |
| | Dentist            2/5  |  |  [x] A-b-c-                12  |
| | Cleaning + check-up     |  |  [ ] Def                    0  |
| '-------------------------'  |  [x] G-h-i-                 5  |
| .-------------------------.  |  [ ] Jkl                    2  |
| | Anna's birthday         |  |                                |
| '-------------------------'  |                                |
+---------------------------------------------------------------+

Calendar events are rounded cards: title on top, the event description as a
smaller subtitle underneath.  Habits are a checklist ticked from a phone, with
the current streak right-aligned.

The panel is written only when displayed content changes — the clock each
minute, the other columns when their data differs.  All use a flicker-free
partial refresh.
"""
from __future__ import annotations

from PIL import Image

from display import fonts
from display.runtime import Screen
from apps.dashboard import data
from integrations import google_calendar as gcal
from integrations import open_meteo
from apps.dashboard.screens import weather_icons

MARGIN = 28
TOP_H = 124          # height of the top clock/weather band

# Event cards
CAL_Y0 = TOP_H + 18  # top of the first card
BOX_PAD_X = 12
BOX_PAD_Y = 9
BOX_GAP = 9
BOX_RADIUS = 10
TITLE_LH = 23        # line height for the title font
DESC_LH = 19         # line height for the description font
MAX_TITLE_LINES = 2
MAX_DESC_LINES = 2
MARKER_GAP = 10      # space between the title and the "2/5" span marker
NOTE_H = 22          # reserved footer for the staleness note
MORE_H = 24          # reserved footer for "+N more"

# Habit checklist (right column)
HAB_Y0 = TOP_H + 60   # first row, below the header
HAB_ROW_H = 33
HAB_BOX = 17          # checkbox side
HAB_BOX_GAP = 13      # gap between checkbox and label

# Weather icon, sized to the space left of the temperature in the top band.
WX_ICON_R = 28       # radius; the glyph occupies roughly 2r
WX_ICON_CY = 56      # vertical centre, balanced against temp + condition lines
WX_ICON_GAP = 24     # clear space between the icon and the temperature


class DashboardScreen(Screen):
    def __init__(self, sm):
        super().__init__(sm)
        self._last_minute: str | None = None
        self._cal_version: int | None = None
        self._wx_version: int | None = None
        self._hab_version: int | None = None

    def on_enter(self) -> None:
        self.sm.mark_dirty("full")

    # No buttons on this device.
    def handle(self, event) -> None:  # noqa: D401
        pass

    def poll(self) -> None:
        """Redraw when the clock ticks or the calendar changes — nothing else."""
        if (self._last_minute is None or self._cal_version is None
                or self._wx_version is None or self._hab_version is None):
            # on_enter already queued a full refresh; marking dirty here would
            # downgrade it to partial and leave the old image showing through.
            return

        now = data.get_now().strftime("%H:%M")
        if now != self._last_minute:
            # Partial is flicker-free; rpi.py still forces a full refresh every
            # FULL_REFRESH_INTERVAL partials to clear ghosting.
            self.sm.mark_dirty("partial")
            return
        if data.get_calendar().version != self._cal_version:
            self.sm.mark_dirty("partial")
            return
        if data.get_weather_snapshot().version != self._wx_version:
            self.sm.mark_dirty("partial")
            return
        if data.get_habits().version != self._hab_version:
            self.sm.mark_dirty("partial")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> Image.Image:
        img, draw = self.blank_canvas()

        now = data.get_now()
        self._last_minute = now.strftime("%H:%M")

        # Read each snapshot once: reading twice could straddle a publish and
        # render an inconsistent frame.
        cal = data.get_calendar()
        # Record the version actually drawn, not poll()'s, or a publish in
        # between would redraw content already on screen.
        self._cal_version = cal.version

        wx = data.get_weather_snapshot()
        self._wx_version = wx.version

        self._draw_top(draw, now, wx)
        # Divider under the top band
        draw.line([(MARGIN, TOP_H), (self.WIDTH - MARGIN, TOP_H)], fill="black", width=2)
        # Vertical divider between the two bottom columns
        mid_x = self.WIDTH // 2
        draw.line([(mid_x, TOP_H + 16), (mid_x, self.HEIGHT - MARGIN)], fill="black", width=1)

        self._draw_calendar(draw, cal, x0=MARGIN, x1=mid_x - 20)
        hab = data.get_habits()
        self._hab_version = hab.version
        self._draw_habits(draw, hab, x0=mid_x + 24, x1=self.WIDTH - MARGIN)

        return img

    def _draw_top(self, draw, now, wx) -> None:
        f_clock = fonts.load(68, bold=True)
        f_date = fonts.load(23)

        draw.text((MARGIN, 12), now.strftime("%H:%M"), font=f_clock, fill="black")
        # "%-d" (no zero padding) is a glibc/BSD extension — fine on both macOS
        # and Raspberry Pi OS, but it is not portable to Windows.
        date_str = now.strftime("%A, %B %-d") if hasattr(now, "strftime") else ""
        draw.text((MARGIN + 3, 90), date_str, font=f_date, fill="black")

        # Weather block, right-aligned
        f_temp = fonts.load(42, bold=True)
        f_cond = fonts.load(21)
        w = wx.weather

        if w.get("temp_c") is None:
            temp_str = "--°C / --°F"
            cond_str = ("Weather loading..." if wx.status == open_meteo.LOADING
                        else "Weather unavailable")
        else:
            temp_str = f"{w['temp_c']}°C / {w['temp_f']}°F"
            cond_str = f"{w['description']} · {w['wind']} {w['wind_unit']}"

        temp_w = _text_w(draw, temp_str, f_temp)
        temp_x = self.WIDTH - MARGIN - temp_w
        draw.text((temp_x, 30), temp_str, font=f_temp, fill="black")

        # The condition line shares a row with the date, so clamp it to the
        # space actually left rather than letting a long one overlap.
        cond_limit = self.WIDTH - MARGIN - (MARGIN + _text_w(draw, date_str, f_date) + 24)
        cond_str = _ellipsize(draw, cond_str, f_cond, cond_limit)
        cond_w = _text_w(draw, cond_str, f_cond)
        draw.text((self.WIDTH - MARGIN - cond_w, 84), cond_str, font=f_cond, fill="black")

        weather_icons.draw_icon(
            draw, w.get("icon"),
            cx=temp_x - WX_ICON_GAP - WX_ICON_R, cy=WX_ICON_CY, r=WX_ICON_R,
        )

    def _draw_calendar(self, draw, cal, x0, x1) -> None:
        f_title = fonts.load(18)
        f_desc = fonts.load(15)
        f_small = fonts.load(14)

        bottom = self.HEIGHT - MARGIN

        # Freshness marker, pinned to the bottom of the column.  Staleness is
        # derived from the snapshot's age, so it also catches a refresh thread
        # that died or hung rather than only a clean failure.  Reserving the
        # space up front means a full column can never paint over it.
        note = ""
        if cal.status == gcal.OK and cal.is_stale():
            note = f"as of {cal.fetched_at_label()}" if cal.fetched_at else "stale"
        elif cal.partial:
            note = "partial"
        if note:
            bottom -= NOTE_H
            draw.text((x1 - _text_w(draw, note, f_small), bottom + 4),
                      note, font=f_small, fill="black")

        y = CAL_Y0

        # Guard against a snapshot for a different day ever reaching the screen:
        # yesterday's all-day events shown as today's is worse than showing none.
        events = cal.events if cal.day == gcal.today() else ()

        if not events:
            draw.text((x0, y), _empty_text(cal), font=f_title, fill="black")
            if cal.status == gcal.AUTH_REQUIRED:
                draw.text((x0, y + 28),
                          "python -m integrations.google_calendar",
                          font=f_small, fill="black")
            return

        inner_w = (x1 - x0) - 2 * BOX_PAD_X
        overflow = 0

        for i, ev in enumerate(events):
            marker = ""
            title_w = inner_w
            if ev.get("days_total", 1) > 1:
                marker = f"{ev.get('day_index', 0) + 1}/{ev['days_total']}"
                title_w -= _text_w(draw, marker, f_small) + MARKER_GAP

            title_lines = _wrap(draw, ev.get("title") or "(no title)",
                                f_title, title_w, MAX_TITLE_LINES)
            desc_lines = _wrap(draw, ev.get("description", ""),
                               f_desc, inner_w, MAX_DESC_LINES)

            h = (2 * BOX_PAD_Y
                 + len(title_lines) * TITLE_LH
                 + len(desc_lines) * DESC_LH)

            # Anything after this one needs a "+N more" line, so reserve it
            # before deciding whether this card fits.
            reserve = MORE_H if i < len(events) - 1 else 0
            if y + h + reserve > bottom:
                overflow = len(events) - i
                break

            draw.rounded_rectangle([(x0, y), (x1, y + h)],
                                   radius=BOX_RADIUS, outline="black", width=1)

            ty = y + BOX_PAD_Y
            for line in title_lines:
                draw.text((x0 + BOX_PAD_X, ty), line, font=f_title, fill="black")
                ty += TITLE_LH
            # The span marker sits on the first title line, right-aligned.
            if marker:
                draw.text((x1 - BOX_PAD_X - _text_w(draw, marker, f_small),
                           y + BOX_PAD_Y + 4), marker, font=f_small, fill="black")
            for line in desc_lines:
                draw.text((x0 + BOX_PAD_X, ty), line, font=f_desc, fill="black")
                ty += DESC_LH

            y += h + BOX_GAP

        if overflow and y + MORE_H <= bottom:
            draw.text((x0 + BOX_PAD_X, y + 2), f"+{overflow} more",
                      font=f_desc, fill="black")

    def _draw_habits(self, draw, hab, x0, x1) -> None:
        f_head = fonts.load(20, bold=True)
        f_item = fonts.load(19)
        f_small = fonts.load(15)

        y = TOP_H + 26
        draw.text((x0, y), "TODAY", font=f_head, fill="black")

        if not hab.configured:
            draw.text((x0, HAB_Y0), "No habits configured", font=f_item, fill="black")
            draw.text((x0, HAB_Y0 + 26), "See private/README.md",
                      font=f_small, fill="black")
            return

        done_count, total = hab.progress()
        prog = f"{done_count}/{total}"
        draw.text((x1 - _text_w(draw, prog, f_head), y), prog, font=f_head, fill="black")

        label_x = x0 + HAB_BOX + HAB_BOX_GAP
        row_y = HAB_Y0

        for name in hab.habits:
            done = name in hab.done
            box_y = row_y + 2
            box = [(x0, box_y), (x0 + HAB_BOX, box_y + HAB_BOX)]

            if done:
                draw.rounded_rectangle(box, radius=4, fill="black")
                # Drawn, not a glyph: CommitMono has no check mark.
                cx, cy = x0 + HAB_BOX / 2, box_y + HAB_BOX / 2
                draw.line([(cx - 4, cy), (cx - 1, cy + 3.5), (cx + 4.5, cy - 4)],
                          fill="white", width=2)
            else:
                draw.rounded_rectangle(box, radius=4, outline="black", width=2)

            streak = hab.streaks.get(name, 0)
            streak_str = str(streak) if streak else ""
            streak_w = _text_w(draw, streak_str, f_small) if streak_str else 0
            if streak_str:
                draw.text((x1 - streak_w, row_y + 3), streak_str,
                          font=f_small, fill="black")

            label_limit = x1 - label_x - (streak_w + 10 if streak_str else 0)
            label = _ellipsize(draw, name, f_item, label_limit)
            draw.text((label_x, row_y), label, font=f_item, fill="black")

            if done:
                # Strikethrough reads from across the room; a checkbox alone does not.
                w = _text_w(draw, label, f_item)
                mid = row_y + 11
                draw.line([(label_x, mid), (label_x + w, mid)], fill="black", width=2)

            row_y += HAB_ROW_H


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


def _ellipsize(draw, text, font, max_w, force: bool = False) -> str:
    """Trim `text` so it fits `max_w`, appending an ellipsis.

    `force` appends the ellipsis even when the text already fits — used by
    _wrap() to mark a line that had more text after it.

    Uses "..." rather than the single-character U+2026: if the bundled font
    lacks that glyph you get a visible tofu box instead.
    """
    if not force and _text_w(draw, text, font) <= max_w:
        return text
    ell = "..."
    while text and _text_w(draw, text + ell, font) > max_w:
        text = text[:-1]
    return (text.rstrip() + ell) if text else ell


def _wrap(draw, text, font, max_w, max_lines) -> list[str]:
    """Word-wrap `text` into at most `max_lines` lines that each fit `max_w`.

    Anything that does not fit is dropped and the last line is ellipsized, so a
    long title degrades to "two lines then ..." instead of running into the
    training column.
    """
    words = (text or "").split()
    if not words or max_lines <= 0 or max_w <= 0:
        return []

    lines: list[str] = []
    current = ""
    i = 0
    while i < len(words) and len(lines) < max_lines:
        trial = f"{current} {words[i]}" if current else words[i]
        if current and _text_w(draw, trial, font) > max_w:
            lines.append(current)
            current = ""
            continue          # retry this word on the next line
        current = trial
        i += 1

    if current and len(lines) < max_lines:
        lines.append(current)
        current = ""

    # A single word wider than the column never wraps above, so every line is
    # ellipsized defensively rather than trusting the measurements.
    lines = [_ellipsize(draw, line, font, max_w) for line in lines]
    if (i < len(words) or current) and lines:
        lines[-1] = _ellipsize(draw, lines[-1], font, max_w, force=True)
    return lines
