"""
Command-line entry point.

    python -m integrations.google_calendar            # one-time OAuth consent
    python -m integrations.google_calendar --check    # print what the API returns
"""
import sys

from .auth import bootstrap, check

if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(check())
    bootstrap()
