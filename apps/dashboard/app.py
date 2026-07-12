"""
Dashboard app definition.

Landscape, no buttons.  Shows clock/date, weather, calendar events and the
running training plan.  Data currently comes from a hardcoded stub
(apps/dashboard/data.py) — swap that module for real APIs later.
"""
from display.runtime import App, LANDSCAPE


def _build_root(sm):
    from apps.dashboard.screens.dashboard import DashboardScreen
    return DashboardScreen(sm)


APP = App(
    name="dashboard",
    size=LANDSCAPE,
    build_root=_build_root,
    uses_input=False,
)
