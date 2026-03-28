"""
SQLite database layer.
Stores books, reading progress, and settings.
"""
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field


DB_PATH = Path(__file__).parent.parent / "data" / "ereader.db"


@dataclass
class Book:
    id: int
    title: str
    author: str
    filepath: str
    total_pages: int
    current_page: int
    added_at: str
    cover_path: str = ""
    year: str = ""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                author       TEXT NOT NULL DEFAULT 'Unknown',
                filepath     TEXT NOT NULL UNIQUE,
                total_pages  INTEGER NOT NULL DEFAULT 0,
                current_page INTEGER NOT NULL DEFAULT 0,
                added_at     TEXT NOT NULL DEFAULT (datetime('now')),
                cover_path   TEXT NOT NULL DEFAULT '',
                year         TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Migrate existing databases that predate the new columns
        for col, default in [("cover_path", "''"), ("year", "''")]:
            try:
                conn.execute(f"ALTER TABLE books ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")
            except sqlite3.OperationalError:
                pass  # column already exists


# ------------------------------------------------------------------
# Books
# ------------------------------------------------------------------

def add_book(title: str, author: str, filepath: str, year: str = "") -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO books (title, author, filepath, year) VALUES (?,?,?,?)",
            (title, author, str(filepath), year),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM books WHERE filepath=?", (str(filepath),)).fetchone()
        return row["id"]


def get_all_books() -> list[Book]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM books ORDER BY added_at DESC").fetchall()
        return [_row_to_book(r) for r in rows]


def get_book_by_id(book_id: int) -> Book | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        return _row_to_book(row) if row else None


def get_book_by_path(filepath: str) -> Book | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM books WHERE filepath=?", (str(filepath),)).fetchone()
        return _row_to_book(row) if row else None


def update_progress(book_id: int, current_page: int, total_pages: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE books SET current_page=?, total_pages=? WHERE id=?",
            (current_page, total_pages, book_id),
        )


def update_cover(book_id: int, cover_path: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE books SET cover_path=? WHERE id=?", (cover_path, book_id))


def delete_book(book_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------

def _row_to_book(row: sqlite3.Row) -> Book:
    d = dict(row)
    return Book(
        id=d["id"],
        title=d["title"],
        author=d["author"],
        filepath=d["filepath"],
        total_pages=d["total_pages"],
        current_page=d["current_page"],
        added_at=d["added_at"],
        cover_path=d.get("cover_path", ""),
        year=d.get("year", ""),
    )
