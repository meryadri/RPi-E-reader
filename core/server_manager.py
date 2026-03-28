"""
Flask server lifecycle manager.
Start / stop the upload server from the e-reader settings screen
without running a separate process.
"""
from __future__ import annotations
import threading
from werkzeug.serving import make_server

_srv = None
_thread: threading.Thread | None = None
PORT = 3003


def start() -> None:
    global _srv, _thread
    if _srv is not None:
        return
    from upload_server import app
    from data.database import init_db
    init_db()
    _srv = make_server("0.0.0.0", PORT, app)
    _thread = threading.Thread(target=_srv.serve_forever, daemon=True)
    _thread.start()


def stop() -> None:
    global _srv, _thread
    if _srv:
        _srv.shutdown()
        _srv = None
        _thread = None


def is_running() -> bool:
    return _srv is not None
