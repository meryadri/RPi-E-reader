"""
E-reader app definition.

Portrait, button-driven EPUB reader.  The wireless upload site is started
from the Settings screen (apps/ereader/server.py) and is internal to the app.
"""
from display.runtime import App, PORTRAIT
from apps.ereader.database import init_db


def _build_root(sm):
    from apps.ereader.screens.library import LibraryScreen
    return LibraryScreen(sm)


APP = App(
    name="ereader",
    size=PORTRAIT,
    build_root=_build_root,
    uses_input=True,
    setup=init_db,
)
