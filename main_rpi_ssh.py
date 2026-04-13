"""
Entry point for Raspberry Pi with SSH keyboard control.

Use this for the first test: e-ink screen shows the output while you
control the reader from your computer keyboard over SSH.

Once physical buttons are wired, switch to main_rpi.py.
"""
import sys
import time
from data.database import init_db
from hal.rpi_ssh import RpiSshDisplay
from core.state_machine import StateMachine
from screens.library import LibraryScreen

TARGET_FPS = 10
FRAME_TIME = 1.0 / TARGET_FPS


def main():
    init_db()

    display = RpiSshDisplay()
    sm = StateMachine(display)
    sm.switch(LibraryScreen(sm))

    print("E-Reader running — use arrow keys, Enter, Esc, m, q")

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
