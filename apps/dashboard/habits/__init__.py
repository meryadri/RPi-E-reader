"""
Daily habit checklist for the dashboard.

The habit names and completion log live in private/, which is gitignored — see
private/README.md.

    from apps.dashboard import habits

    habits.start()                  # once, from App.setup
    snap = habits.get_snapshot()    # never blocks, never raises
"""
from .service import Snapshot, get_snapshot, get_log, is_running, reload_from_disk, start, stop, toggle  # noqa: F401
from .server import start as start_server, stop as stop_server, url  # noqa: F401

__all__ = [
    "Snapshot", "get_snapshot", "get_log", "is_running", "reload_from_disk",
    "start", "stop", "toggle", "start_server", "stop_server", "url",
]
