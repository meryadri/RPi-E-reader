# Weather integration (Open-Meteo)

Current conditions for the dashboard: temperature in **°C and °F**, a condition
**icon**, **wind speed** and a short **description**.

**There is no setup.** [Open-Meteo](https://open-meteo.com) needs no API key and
no account, so there is nothing to create, copy to the Pi, rotate, or have
expire. It works out of the box.

The only thing you might want to change is the location.

---

## Location

Defaults to Boston, MA. Override with environment variables, or edit
`config.py`:

```bash
WEATHER_LAT=51.5072 WEATHER_LON=-0.1276 python main.py --app dashboard
```

Find coordinates for any place with Open-Meteo's free geocoding endpoint:

```bash
curl 'https://geocoding-api.open-meteo.com/v1/search?name=<city>&count=5'
```

## Checking it works

```bash
python -m integrations.open_meteo
```

Prints the request URL and the current reading as plain text. Works over SSH and
separates "the API is broken" from "the display is broken".

```
Location: 42.325, -71.085

  20°C / 67°F
  Feels like 22°C / 71°F
  Heavy rain  [icon: rain]
  Wind 8 km/h
  Daytime: True
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `WEATHER_LAT` | `42.325` | Latitude |
| `WEATHER_LON` | `-71.085` | Longitude |
| `WEATHER_WIND_UNIT` | `kmh` | `kmh`, `mph`, `ms` or `kn` |
| `WEATHER_REFRESH_SECONDS` | `900` | Poll interval (15 min) |
| `WEATHER_STALE_AFTER` | `3600` | Age at which the reading counts as stale |

### How often it fetches

Every **15 minutes**, which is roughly how often Open-Meteo updates its
current-conditions data — polling faster only burns power. That's 96 requests a
day, far inside their fair-use guidance for non-commercial use.

On failure it backs off 30s → 60s → 120s → 300s, keeping the last good reading
on screen meanwhile.

**A fetch returning the same values writes nothing to the e-ink panel.**
Temperatures and wind are rounded to whole units before comparison, so drifting
from 18.2° to 18.4° does not trigger a refresh.

## Icons

Rendered from the bundled **[Weather Icons](https://github.com/erikflowers/weather-icons)**
font by Erik Flowers (SIL OFL 1.1), at `assets/fonts/weathericons-regular-webfont.ttf`.
Monochrome vector glyphs suit a 1-bit panel well.

Nine icons, chosen to match what WMO codes actually distinguish:

| Icon | Conditions |
|---|---|
| `clear` / `clear_night` | Clear sky |
| `partly` / `partly_night` | Mainly clear, partly cloudy |
| `cloudy` | Overcast |
| `fog` | Fog, freezing fog |
| `rain` | Drizzle, rain, showers, freezing rain |
| `snow` | Snow, snow grains, snow showers |
| `thunder` | Thunderstorm, hail |

If the font file is missing, `weather_icons.py` falls back to shapes drawn from
Pillow primitives — plainer, but the corner is never blank.

## Layout

| File | Role |
|---|---|
| `config.py` | Location, units, intervals — all env-overridable |
| `client.py` | The single HTTP GET (stdlib `urllib`, 10s timeout) |
| `conditions.py` | Pure WMO-code → icon/description, °C → °F — unit tested |
| `cache.py` | Last-good reading at `data/weather_cache.json` |
| `service.py` | Refresh thread and the immutable snapshot apps read |
| `__main__.py` | The `python -m integrations.open_meteo` check |

`conditions.py` holds all the interpretation logic and touches no network, so
`tests/test_weather_conditions.py` can sweep every documented WMO code offline.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `--°C / --°F` and "Weather loading..." | First fetch hasn't landed yet; it appears within 30s |
| `--°C / --°F` and "Weather unavailable" | No network, and no cached reading to fall back on |
| Wrong location | Set `WEATHER_LAT` / `WEATHER_LON` |
| Plain-looking icons | The Weather Icons font is missing from `assets/fonts/` — the drawn fallback is in use |
| Temperature never updates | Check `python -m integrations.open_meteo` still fetches; the panel only redraws when rounded values change |
