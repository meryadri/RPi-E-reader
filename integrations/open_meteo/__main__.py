"""
Command-line entry point.

    python -m integrations.open_meteo

Prints current conditions as plain text.  Works over SSH and separates "the API
is broken" from "the display is broken".
"""
from __future__ import annotations

import sys

from . import client, config


def main() -> int:
    print(f"Location: {config.LATITUDE}, {config.LONGITUDE}")
    print(f"URL: {client.build_url(config.LATITUDE, config.LONGITUDE)}\n")
    try:
        w = client.fetch()
    except Exception as exc:
        print(f"FETCH FAILED: {exc}")
        return 1

    print(f"  {w['temp_c']}°C / {w['temp_f']}°F")
    print(f"  Feels like {w['feels_c']}°C / {w['feels_f']}°F")
    print(f"  {w['description']}  [icon: {w['icon']}]")
    print(f"  Wind {w['wind']} {w['wind_unit']}")
    print(f"  Daytime: {w['is_day']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
