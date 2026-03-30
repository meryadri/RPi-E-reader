"""
Entry point for Raspberry Pi hardware.
Swap this in place of main.py when running on the Pi.
"""
import sys
import time
from data.database import init_db
from hal.rpi import RpiDisplay
from core.state_machine import StateMachine
from screens.library import LibraryScreen

# E-ink is slow — no point running faster than the panel can refresh.
# The state machine only pushes a new image when something has changed.
TARGET_FPS = 10
FRAME_TIME = 1.0 / TARGET_FPS


def main():
    init_db()

    display = RpiDisplay()
    sm = StateMachine(display)
    sm.switch(LibraryScreen(sm))

    while display.is_running():
        t0 = time.monotonic()
        event = display.poll_event()
        sm.tick(event)
        elapsed = time.monotonic() - t0
        sleep = FRAME_TIME - elapsed
        if sleep > 0:
            time.sleep(sleep)

    sys.exit(0)


if __name__ == "__main__":
    main()
