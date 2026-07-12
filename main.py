"""
Launcher.

    python main.py --app ereader   [--backend sim]       # portrait e-reader
    python main.py --app dashboard [--backend sim]       # landscape dashboard

Backends:
    sim       laptop pygame window (default)
    rpi       Raspberry Pi + Waveshare e-ink, GPIO buttons
    rpi_ssh   Raspberry Pi + Waveshare e-ink, keyboard over SSH

The launcher reads the app's orientation and builds the display backend at the
matching size, then hands off to the shared runtime loop.
"""
import argparse
import importlib
import sys

from display.runtime import run

# E-ink is slow — no point running faster than the panel refreshes.
_FPS = {"sim": 30, "rpi": 10, "rpi_ssh": 10}


def _make_display(backend: str, width: int, height: int):
    if backend == "sim":
        from display.hal.simulator import SimulatorDisplay
        return SimulatorDisplay(width, height)
    if backend == "rpi":
        from display.hal.rpi import RpiDisplay
        return RpiDisplay(width, height)
    if backend == "rpi_ssh":
        from display.hal.rpi_ssh import RpiSshDisplay
        return RpiSshDisplay(width, height)
    raise ValueError(f"Unknown backend: {backend}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E-ink app launcher")
    parser.add_argument("--app", required=True, choices=["ereader", "dashboard"])
    parser.add_argument("--backend", default="sim", choices=["sim", "rpi", "rpi_ssh"])
    args = parser.parse_args()

    app = importlib.import_module(f"apps.{args.app}.app").APP
    width, height = app.size
    display = _make_display(args.backend, width, height)

    try:
        run(app, display, target_fps=_FPS[args.backend])
    finally:
        cleanup = getattr(display, "cleanup", None)
        if callable(cleanup):
            cleanup()
        if args.backend == "sim":
            import pygame
            pygame.quit()

    sys.exit(0)


if __name__ == "__main__":
    main()
