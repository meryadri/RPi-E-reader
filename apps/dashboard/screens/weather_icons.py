"""
Weather icons.

Primary path is the bundled **Weather Icons** font (Erik Flowers, SIL OFL 1.1) —
a standard, widely used icon set, rendered as glyphs through the normal
display.fonts loader.  Monochrome vector glyphs suit a 1-bit panel well.

If that font is missing, everything falls back to shapes drawn from Pillow
primitives, so a deploy that forgets the asset degrades to plainer icons rather
than a blank corner.

Every function takes (draw, cx, cy, r) and centres the icon on (cx, cy) within
roughly a 2r box.
"""
from __future__ import annotations

import math

from display import fonts
from integrations.open_meteo import conditions as C

# Weather Icons codepoints (Private Use Area).  Verified to render non-blank
# against the bundled font; see tests/test_weather_conditions.py.
GLYPHS = {
    C.CLEAR:        "\uf00d",   # wi-day-sunny
    C.CLEAR_NIGHT:  "\uf02e",   # wi-night-clear
    C.PARTLY:       "\uf002",   # wi-day-cloudy
    C.PARTLY_NIGHT: "\uf086",   # wi-night-alt-cloudy
    C.CLOUDY:       "\uf013",   # wi-cloudy
    C.FOG:          "\uf014",   # wi-fog
    C.RAIN:         "\uf019",   # wi-rain
    C.SNOW:         "\uf01b",   # wi-snow
    C.THUNDER:      "\uf01e",   # wi-thunderstorm
}


def draw_icon(draw, kind: str | None, cx: int, cy: int, r: int) -> None:
    """Draw a weather icon centred on (cx, cy).  Unknown kind draws nothing."""
    if kind is None:
        return

    glyph = GLYPHS.get(kind)
    if glyph is not None:
        # ~2.2r gives a glyph roughly 2r tall for this font's metrics.
        font = fonts.load(int(r * 2.2), font_name=fonts.WEATHER)
        if font is not None:
            draw.text((cx, cy), glyph, font=font, fill="black", anchor="mm")
            return

    fn = _DRAWN.get(kind)
    if fn is not None:
        fn(draw, cx, cy, r)


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------

def _sun(draw, cx, cy, r, rays=True) -> None:
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline="black", width=3)
    if not rays:
        return
    for i in range(8):
        a = math.pi * i / 4
        draw.line(
            [(cx + math.cos(a) * (r + 5), cy + math.sin(a) * (r + 5)),
             (cx + math.cos(a) * (r + 13), cy + math.sin(a) * (r + 13))],
            fill="black", width=3,
        )


def _cloud(draw, cx, cy, r, width=3) -> None:
    """A cloud whose body sits on the line y = cy + r*0.45."""
    base = cy + r * 0.45
    draw.ellipse([(cx - r, base - r * 0.75), (cx, base + r * 0.25)],
                 outline="black", fill="white", width=width)
    draw.ellipse([(cx - r * 0.35, base - r * 1.05), (cx + r * 0.75, base + r * 0.25)],
                 outline="black", fill="white", width=width)
    # Flatten the underside into a single edge.
    draw.rectangle([(cx - r * 0.85, base - r * 0.1), (cx + r * 0.6, base + r * 0.2)],
                   fill="white")
    draw.line([(cx - r * 0.85, base + r * 0.2), (cx + r * 0.62, base + r * 0.2)],
              fill="black", width=width)


def _drops(draw, cx, cy, r, n=3) -> None:
    top = cy + r * 0.75
    for i in range(n):
        x = cx - r * 0.6 + i * (r * 0.6)
        draw.line([(x, top), (x - r * 0.18, top + r * 0.55)], fill="black", width=3)


def _flakes(draw, cx, cy, r, n=3) -> None:
    top = cy + r * 1.0
    for i in range(n):
        x = cx - r * 0.6 + i * (r * 0.6)
        for a in (0, math.pi / 3, 2 * math.pi / 3):
            dx, dy = math.cos(a) * r * 0.22, math.sin(a) * r * 0.22
            draw.line([(x - dx, top - dy), (x + dx, top + dy)], fill="black", width=2)


def _bolt(draw, cx, cy, r) -> None:
    top = cy + r * 0.7
    draw.polygon(
        [(cx + r * 0.12, top),
         (cx - r * 0.38, top + r * 0.62),
         (cx - r * 0.04, top + r * 0.62),
         (cx - r * 0.26, top + r * 1.15),
         (cx + r * 0.42, top + r * 0.48),
         (cx + r * 0.04, top + r * 0.48)],
        fill="black",
    )


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

def _clear(draw, cx, cy, r) -> None:
    _sun(draw, cx, cy, int(r * 0.82))


def _clear_night(draw, cx, cy, r) -> None:
    """Crescent moon: a filled disc with an offset disc punched out of it."""
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill="black")
    off = int(r * 0.55)
    draw.ellipse([(cx - r + off, cy - r - int(r * 0.12)),
                  (cx + r + off, cy + r - int(r * 0.12))], fill="white")


def _partly(draw, cx, cy, r) -> None:
    _sun(draw, cx + r * 0.42, cy - r * 0.45, int(r * 0.46))
    _cloud(draw, cx - r * 0.12, cy + r * 0.1, r * 0.82)


def _cloudy(draw, cx, cy, r) -> None:
    _cloud(draw, cx, cy - r * 0.1, r)


def _fog(draw, cx, cy, r) -> None:
    _cloud(draw, cx, cy - r * 0.35, r * 0.9)
    for i in range(3):
        y = cy + r * (0.75 + i * 0.32)
        inset = r * (0.15 if i % 2 else 0.0)
        draw.line([(cx - r * 0.8 + inset, y), (cx + r * 0.8 - inset, y)],
                  fill="black", width=3)


def _rain(draw, cx, cy, r) -> None:
    _cloud(draw, cx, cy - r * 0.35, r * 0.92)
    _drops(draw, cx, cy, r)


def _snow(draw, cx, cy, r) -> None:
    _cloud(draw, cx, cy - r * 0.35, r * 0.92)
    _flakes(draw, cx, cy, r)


def _thunder(draw, cx, cy, r) -> None:
    _cloud(draw, cx, cy - r * 0.35, r * 0.92)
    _bolt(draw, cx, cy, r)


_DRAWN = {
    C.CLEAR: _clear,
    C.CLEAR_NIGHT: _clear_night,
    C.PARTLY: _partly,
    C.PARTLY_NIGHT: _partly,
    C.CLOUDY: _cloudy,
    C.FOG: _fog,
    C.RAIN: _rain,
    C.SNOW: _snow,
    C.THUNDER: _thunder,
}

# Every icon the conditions module can return must be renderable both ways.
assert set(_DRAWN) == set(C.ICONS), set(C.ICONS) ^ set(_DRAWN)
assert set(GLYPHS) == set(C.ICONS), set(C.ICONS) ^ set(GLYPHS)
