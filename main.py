"""
Entry point for the laptop simulator.
Runs the state machine + pygame event loop.
"""
import sys
import time
from data.database import init_db
from hal.simulator import SimulatorDisplay
from core.state_machine import StateMachine
from screens.library import LibraryScreen

TARGET_FPS = 30
FRAME_TIME = 1.0 / TARGET_FPS


def main():
    init_db()

    display = SimulatorDisplay()
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

    import pygame
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
