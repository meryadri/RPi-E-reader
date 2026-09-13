"""
Dev utility — wipes uploaded books and the database so you can start fresh.
Leaves the database schema intact by re-initialising it after deletion.

Usage:
    python dev_reset.py
"""
import shutil
from pathlib import Path

ROOT     = Path(__file__).parent
DB       = ROOT / "data" / "ereader.db"
COVERS   = ROOT / "data" / "covers"
UPLOADS  = ROOT / "uploads"
METRICS  = ROOT / "data" / "metrics_cache.pkl"
CALENDAR = ROOT / "data" / "calendar_cache.json"

def confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N] ").strip().lower() == "y"

def main():
    print("This will delete:")
    print(f"  {DB}")
    print(f"  {COVERS}/ (all cover images)")
    print(f"  {UPLOADS}/ (all uploaded EPUBs)")
    print(f"  {METRICS} (word-width cache)")
    print(f"  {CALENDAR} (cached calendar events)")
    print()
    print("Your Google credentials are NOT touched.")
    print()
    if not confirm("Continue?"):
        print("Aborted.")
        return

    if DB.exists():
        DB.unlink()
        print(f"Deleted {DB}")

    if COVERS.exists():
        shutil.rmtree(COVERS)
        print(f"Deleted {COVERS}/")

    if UPLOADS.exists():
        shutil.rmtree(UPLOADS)
        UPLOADS.mkdir()
        print(f"Cleared {UPLOADS}/")

    if METRICS.exists():
        METRICS.unlink()
        print(f"Deleted {METRICS}")

    if CALENDAR.exists():
        CALENDAR.unlink()
        print(f"Deleted {CALENDAR}")

    # Re-initialise the database schema
    from apps.ereader.database import init_db
    init_db()
    print("Database re-initialised.")
    print("\nDone — clean slate.")

if __name__ == "__main__":
    main()
