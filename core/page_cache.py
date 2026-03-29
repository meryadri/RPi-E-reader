"""
In-memory page cache.

Key: (book_id, font_size, font_name)
Value: list[Page]

Holds at most MAX_ENTRIES books at once. When full, the least-recently-used
entry is evicted. This keeps memory bounded on the Pi while still making
re-opening the same book with the same settings instant.
"""
from __future__ import annotations
from core.paginator import Page

MAX_ENTRIES = 16

_cache: dict[tuple, list[Page]] = {}
_lru:   list[tuple]             = []   # front = oldest, back = most recent


def get(key: tuple) -> list[Page] | None:
    if key not in _cache:
        return None
    # Move to most-recently-used position
    _lru.remove(key)
    _lru.append(key)
    return _cache[key]


def put(key: tuple, pages: list[Page]) -> None:
    if key in _cache:
        _lru.remove(key)
    elif len(_cache) >= MAX_ENTRIES:
        evict = _lru.pop(0)
        del _cache[evict]
    _cache[key] = pages
    _lru.append(key)


def invalidate(book_id: int) -> None:
    """Drop all cached entries for a book (call after re-upload or deletion)."""
    stale = [k for k in _cache if k[0] == book_id]
    for k in stale:
        del _cache[k]
        _lru.remove(k)
