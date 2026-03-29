"""
Persistent font metrics cache.

Maps (font_size, font_name) → {word: advance_width_px}.

Words are measured once ever — results survive across paginate() calls and
app restarts via a pickle file at data/metrics_cache.pkl.

If you replace font files, delete data/metrics_cache.pkl so stale widths
are not used with the new glyphs.
"""
from __future__ import annotations
import pickle
from pathlib import Path

_CACHE_FILE = Path(__file__).parent.parent / "data" / "metrics_cache.pkl"

# (font_size, font_name) → {word: float}
_store: dict[tuple, dict[str, float]] = {}
_dirty = False


def _load() -> None:
    global _store
    try:
        if _CACHE_FILE.exists():
            with open(_CACHE_FILE, "rb") as f:
                _store = pickle.load(f)
    except Exception:
        _store = {}


def save() -> None:
    """Write in-memory metrics to disk if anything new was measured."""
    global _dirty
    if not _dirty:
        return
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_CACHE_FILE, "wb") as f:
            pickle.dump(_store, f)
        _dirty = False
    except Exception:
        pass


def slot(font_size: int, font_name: str) -> dict[str, float]:
    """
    Return the word→width dict for this font configuration.
    The caller mutates it directly; call mark_dirty() if new entries are added.
    """
    key = (font_size, font_name)
    if key not in _store:
        _store[key] = {}
    return _store[key]


def mark_dirty() -> None:
    global _dirty
    _dirty = True


def stats() -> dict[tuple, int]:
    """Return {(font_size, font_name): word_count} for diagnostics."""
    return {k: len(v) for k, v in _store.items()}


def clear() -> None:
    """Wipe the in-memory store and delete the cache file (use after font swap)."""
    global _store, _dirty
    _store = {}
    _dirty = False
    try:
        _CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# Load from disk on module import
_load()
