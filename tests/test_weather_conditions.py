"""
Weather logic tests — pure, offline, no network.
"""
import pytest

from integrations.open_meteo import client, conditions as C

# Every code Open-Meteo documents for WMO 4677.
ALL_WMO_CODES = [
    0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
    71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99,
]


# --- code mapping ----------------------------------------------------------

@pytest.mark.parametrize("code", ALL_WMO_CODES)
def test_every_documented_code_maps_to_a_real_icon(code):
    """A gap here would silently render no icon at all for real weather."""
    icon, text = C.describe(code)
    assert icon in C.ICONS
    assert text and text != C.UNKNOWN_DESCRIPTION


@pytest.mark.parametrize("code", ALL_WMO_CODES)
def test_every_description_fits_the_layout_budget(code):
    """The condition line shares a row with the date; long text would overlap."""
    _, text = C.describe(code)
    assert len(text) <= C.MAX_DESCRIPTION, text


@pytest.mark.parametrize("bad", [None, "", "abc", -1, 4242, 7.5])
def test_unknown_code_degrades_instead_of_raising(bad):
    icon, text = C.describe(bad)
    assert icon == C.CLOUDY
    assert text == C.UNKNOWN_DESCRIPTION


def test_clear_at_night_uses_the_moon():
    """A sun at 11pm looks broken."""
    assert C.describe(0, is_day=True)[0] == C.CLEAR
    assert C.describe(0, is_day=False)[0] == C.CLEAR_NIGHT


def test_partly_cloudy_also_has_a_night_variant():
    assert C.describe(2, is_day=True)[0] == C.PARTLY
    assert C.describe(2, is_day=False)[0] == C.PARTLY_NIGHT


def test_only_clear_and_partly_change_with_daylight():
    """Rain at night is still rain — don't invent night variants for everything."""
    for code in ALL_WMO_CODES:
        if code in (0, 1, 2):
            continue
        assert C.describe(code, True)[0] == C.describe(code, False)[0]


def test_representative_codes():
    assert C.describe(3)[0] == C.CLOUDY
    assert C.describe(48)[0] == C.FOG
    assert C.describe(65)[0] == C.RAIN
    assert C.describe(75)[0] == C.SNOW
    assert C.describe(95)[0] == C.THUNDER


# --- unit conversion -------------------------------------------------------

@pytest.mark.parametrize("c,f", [(0, 32), (100, 212), (37, 99), (20, 68), (-40, -40)])
def test_c_to_f(c, f):
    assert C.c_to_f(c) == f


def test_c_to_f_rounds_negatives_correctly():
    """int() truncates toward zero and would be a degree out all winter."""
    assert C.c_to_f(-17.8) == 0
    assert C.c_to_f(-0.6) == 31


# --- response parsing ------------------------------------------------------

SAMPLE = {
    "current": {
        "time": "2026-09-13T12:30",
        "temperature_2m": 20.4,
        "apparent_temperature": 22.1,
        "weather_code": 65,
        "wind_speed_10m": 8.3,
        "is_day": 1,
    }
}


def test_parse_sample_payload():
    w = client.parse(SAMPLE)
    assert w["temp_c"] == 20 and w["temp_f"] == 69
    assert w["feels_c"] == 22
    assert w["icon"] == C.RAIN and w["description"] == "Heavy rain"
    assert w["wind"] == 8 and w["is_day"] is True


def test_parse_always_returns_every_key():
    """render() indexes these unguarded, and run() has no try/except above it."""
    w = client.parse(SAMPLE)
    for key in ("temp_c", "temp_f", "feels_c", "feels_f", "icon",
                "description", "wind", "wind_unit", "is_day"):
        assert w[key] is not None


def test_missing_current_raises_rather_than_publishing_garbage():
    with pytest.raises(ValueError):
        client.parse({})


def test_missing_apparent_temperature_falls_back_to_actual():
    w = client.parse({"current": {"temperature_2m": 12.0, "weather_code": 0}})
    assert w["feels_c"] == w["temp_c"] == 12


def test_missing_wind_is_zero_not_none():
    w = client.parse({"current": {"temperature_2m": 12.0, "weather_code": 0}})
    assert w["wind"] == 0


def test_night_payload_gives_moon():
    payload = {"current": {"temperature_2m": 8.0, "weather_code": 0, "is_day": 0}}
    assert client.parse(payload)["icon"] == C.CLEAR_NIGHT


def test_build_url_includes_location_and_fields():
    url = client.build_url(42.325, -71.085)
    assert "latitude=42.325" in url and "longitude=-71.085" in url
    assert "weather_code" in url and "wind_speed_10m" in url


# --- icons -----------------------------------------------------------------

def test_every_condition_icon_has_a_glyph_and_a_fallback():
    """weather_icons must cover everything conditions.describe() can return."""
    from apps.dashboard.screens import weather_icons
    assert set(weather_icons.GLYPHS) == set(C.ICONS)
    assert set(weather_icons._DRAWN) == set(C.ICONS)


@pytest.mark.parametrize("kind", sorted(C.ICONS))
def test_every_glyph_renders_non_blank(kind):
    """Guards against a wrong codepoint silently drawing nothing (or a tofu box)."""
    from PIL import Image, ImageDraw
    from apps.dashboard.screens import weather_icons
    from display import fonts

    if fonts.load(40, font_name=fonts.WEATHER) is None:
        pytest.skip("weather icon font not bundled")

    img = Image.new("L", (80, 80), 255)
    weather_icons.draw_icon(ImageDraw.Draw(img), kind, 40, 40, 18)
    ink = sum(1 for p in img.get_flattened_data() if p < 128)
    assert ink > 50, f"{kind} rendered {ink} ink pixels"


@pytest.mark.parametrize("kind", sorted(C.ICONS))
def test_fallback_shapes_render_non_blank(kind):
    from PIL import Image, ImageDraw
    from apps.dashboard.screens import weather_icons

    img = Image.new("L", (80, 80), 255)
    weather_icons._DRAWN[kind](ImageDraw.Draw(img), 40, 40, 18)
    ink = sum(1 for p in img.get_flattened_data() if p < 128)
    assert ink > 50, f"{kind} fallback rendered {ink} ink pixels"
