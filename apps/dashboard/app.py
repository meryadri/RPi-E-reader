"""
Dashboard app definition.

Landscape, no buttons.  Shows clock/date, weather, today's all-day calendar
events and the running training plan.

Calendar data is live — see integrations/google_calendar/README.md for setup.
Weather and training still come from the hardcoded stub in data.py.
"""
from display.runtime import App, LANDSCAPE


def _setup():
    from apps.dashboard import data
    data.start_sources()


def _build_root(sm):
    from apps.dashboard.screens.dashboard import DashboardScreen
    return DashboardScreen(sm)


APP = App(
    name="dashboard",
    size=LANDSCAPE,
    build_root=_build_root,
    uses_input=False,
    setup=_setup,
    # No buttons to poll and the clock only needs second-level accuracy, so
    # there is nothing to gain from spinning the loop faster.  This is the
    # event-loop rate, not the panel refresh rate.
    fps=1,
)
