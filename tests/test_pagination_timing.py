"""
Pagination timing and memory tests using a real EPUB.

Run with:
    python -m pytest tests/test_pagination_timing.py -v -s

The -s flag is required to see the timing and memory output printed to stdout.

Timing methodology
------------------
Cold runs  — metrics cache is cleared before every single repetition, so each
             measurement reflects the true worst case (no words pre-measured).
Warm runs  — cache is populated by one throw-away call first; subsequent calls
             only do layout work, with all word widths already known.
Averaging cold and warm together would be misleading, so the two are always
reported separately.
"""
import sys
import time
import statistics
import tracemalloc
from pathlib import Path
import pytest

from core import metrics_cache as _mc
from core.epub_parser import parse_epub
from core.paginator import paginate, _width, DEFAULT_FONT_SIZE, FONT_SIZE_MIN, FONT_SIZE_MAX
from core import fonts

EPUB = Path("tests/leo-tolstoy_war-and-peace.epub")
RUNS = 5   # number of timed repetitions per cold/warm block


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _time_cold(paragraphs, runs=RUNS, **kwargs) -> dict:
    """
    Run paginate() `runs` times, clearing the metrics cache before every run.
    Returns timing stats (ms) that reflect pure cold performance.
    """
    times = []
    pages = None
    for _ in range(runs):
        _mc.clear()
        t0 = time.perf_counter()
        pages = paginate(paragraphs, **kwargs)
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "pages":  len(pages),
        "best":   min(times),
        "worst":  max(times),
        "median": statistics.median(times),
        "stdev":  statistics.stdev(times) if len(times) > 1 else 0.0,
    }


def _time_warm(paragraphs, runs=RUNS, **kwargs) -> dict:
    """
    Pre-populate the metrics cache with one throw-away call, then run
    paginate() `runs` times.  Returns timing stats reflecting warm performance
    (word widths already cached — only layout work remains).
    """
    _mc.clear()
    paginate(paragraphs, **kwargs)   # warm-up: fills the metrics cache
    times = []
    pages = None
    for _ in range(runs):
        t0 = time.perf_counter()
        pages = paginate(paragraphs, **kwargs)
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "pages":  len(pages),
        "best":   min(times),
        "worst":  max(times),
        "median": statistics.median(times),
        "stdev":  statistics.stdev(times) if len(times) > 1 else 0.0,
    }


def _report_cold_warm(label, cold, warm):
    speedup = cold["median"] / max(warm["median"], 0.01)
    print(
        f"\n  {label}\n"
        f"    pages       : {cold['pages']}\n"
        f"    cold median : {cold['median']:.1f} ms  "
        f"(best {cold['best']:.1f} / worst {cold['worst']:.1f} / stdev {cold['stdev']:.1f})\n"
        f"    warm median : {warm['median']:.1f} ms  "
        f"(best {warm['best']:.1f} / worst {warm['worst']:.1f} / stdev {warm['stdev']:.1f})\n"
        f"    speedup     : {speedup:.0f}×"
    )


def _report_cold(label, cold):
    print(
        f"\n  {label}\n"
        f"    pages       : {cold['pages']}\n"
        f"    cold median : {cold['median']:.1f} ms  "
        f"(best {cold['best']:.1f} / worst {cold['worst']:.1f} / stdev {cold['stdev']:.1f})"
    )


def _build_word_cache(paragraphs, font_size, font_name) -> dict:
    """Replicate the word cache paginate() builds internally."""
    font = fonts.load(font_size, font_name=font_name)
    cache = {" ": _width(font, " ")}
    for para in paragraphs:
        for word in para.split():
            if word not in cache:
                cache[word] = _width(font, word)
    return cache


def _cache_memory_kb(cache: dict) -> float:
    total = sys.getsizeof(cache)
    total += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in cache.items())
    return total / 1024


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def book():
    assert EPUB.exists(), f"EPUB not found: {EPUB}"
    return parse_epub(EPUB)


@pytest.fixture(scope="module")
def paragraphs(book):
    return book.full_text_paragraphs


@pytest.fixture(autouse=True)
def clear_metrics_cache():
    """Wipe the metrics cache before every test so tests are independent."""
    _mc.clear()
    yield
    _mc.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPaginationTiming:

    def test_parse_epub_time(self):
        """How long does EPUB parsing alone take?"""
        times = []
        for _ in range(RUNS):
            t0 = time.perf_counter()
            parsed = parse_epub(EPUB)
            times.append((time.perf_counter() - t0) * 1000)
        print(
            f"\n  parse_epub()\n"
            f"    paragraphs  : {len(parsed.full_text_paragraphs):,}\n"
            f"    median      : {statistics.median(times):.1f} ms  "
            f"(best {min(times):.1f} / worst {max(times):.1f})"
        )
        assert statistics.median(times) < 10_000

    def test_default_settings(self, paragraphs):
        """Cold vs warm at default font size and font."""
        cold = _time_cold(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=fonts.COMMIT_MONO)
        warm = _time_warm(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=fonts.COMMIT_MONO)
        _report_cold_warm(f"CommitMono {DEFAULT_FONT_SIZE}px (default)", cold, warm)
        assert cold["worst"] < 10_000

    def test_font_sizes(self, paragraphs):
        """Cold vs warm at two representative sizes (timing is uniform across the range)."""
        print()
        for size in [FONT_SIZE_MIN, FONT_SIZE_MAX]:
            cold = _time_cold(paragraphs, font_size=size, font_name=fonts.COMMIT_MONO)
            warm = _time_warm(paragraphs, font_size=size, font_name=fonts.COMMIT_MONO)
            _report_cold_warm(f"CommitMono {size}px", cold, warm)
            assert cold["worst"] < 10_000

    def test_commit_mono_vs_system(self, paragraphs):
        """Compare CommitMono against the system font — cold worst case only."""
        cold_cm = _time_cold(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=fonts.COMMIT_MONO)
        cold_sy = _time_cold(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=fonts.SYSTEM)
        _report_cold(f"CommitMono {DEFAULT_FONT_SIZE}px", cold_cm)
        _report_cold(f"System     {DEFAULT_FONT_SIZE}px", cold_sy)
        assert cold_cm["worst"] < 10_000
        assert cold_sy["worst"] < 10_000

    def test_word_cache_speedup(self, paragraphs):
        """
        Demonstrate the metrics cache speedup:
        cold run (no words cached) vs warm run (all words pre-measured).
        The warm run should be significantly faster.
        """
        _mc.clear()
        t0 = time.perf_counter()
        paginate(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=fonts.COMMIT_MONO)
        cold_ms = (time.perf_counter() - t0) * 1000

        # Now cache is warm — measure the next call
        t0 = time.perf_counter()
        paginate(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=fonts.COMMIT_MONO)
        warm_ms = (time.perf_counter() - t0) * 1000

        speedup = cold_ms / max(warm_ms, 0.01)
        print(
            f"\n  Metrics cache speedup\n"
            f"    cold (first call)  : {cold_ms:.1f} ms\n"
            f"    warm (second call) : {warm_ms:.1f} ms\n"
            f"    speedup            : {speedup:.0f}×"
        )
        assert warm_ms < cold_ms, "Warm run should be faster than cold run"

    def test_word_cache_memory(self, paragraphs):
        """
        Measure the memory footprint of the word cache built during paginate().
        Reports unique word count and cache size in KB.
        """
        print()
        for font_name, label in [(fonts.COMMIT_MONO, "CommitMono"), (fonts.SYSTEM, "System")]:
            cache = _build_word_cache(paragraphs, DEFAULT_FONT_SIZE, font_name)
            mem_kb = _cache_memory_kb(cache)
            unique_words = len(cache) - 1  # subtract the " " entry
            avg_word_len = sum(len(k) for k in cache if k != " ") / max(unique_words, 1)
            print(
                f"\n  Word cache — {label} {DEFAULT_FONT_SIZE}px\n"
                f"    unique words   : {unique_words:,}\n"
                f"    avg word length: {avg_word_len:.1f} chars\n"
                f"    memory         : {mem_kb:.1f} KB"
            )
            assert mem_kb < 10_000

    def test_paginate_peak_memory(self, paragraphs):
        """
        Measure peak memory allocated by a single cold paginate() call.
        Cache is cleared first so tracemalloc captures word measurement too.
        """
        print()
        for font_name, label in [(fonts.COMMIT_MONO, "CommitMono"), (fonts.SYSTEM, "System")]:
            _mc.clear()
            tracemalloc.start()
            pages = paginate(paragraphs, font_size=DEFAULT_FONT_SIZE, font_name=font_name)
            current_kb, peak_kb = (v / 1024 for v in tracemalloc.get_traced_memory())
            tracemalloc.stop()

            total_lines = sum(len(p.lines) for p in pages)
            print(
                f"\n  Peak memory (cold) — {label} {DEFAULT_FONT_SIZE}px\n"
                f"    pages        : {len(pages)}\n"
                f"    total lines  : {total_lines:,}\n"
                f"    current      : {current_kb:.1f} KB\n"
                f"    peak         : {peak_kb:.1f} KB"
            )
            assert peak_kb < 500_000

    def test_page_cache_hit(self, paragraphs):
        """
        The page_cache in reader.py should make re-opens instant.
        Cold path = clear metrics cache + parse + paginate.
        Warm path = in-memory page cache hit only.
        """
        from core import page_cache

        key = (9999, DEFAULT_FONT_SIZE, fonts.COMMIT_MONO)
        page_cache._cache.pop(key, None)

        _mc.clear()
        t0 = time.perf_counter()
        parsed = parse_epub(EPUB)
        pages  = paginate(parsed.full_text_paragraphs, font_size=DEFAULT_FONT_SIZE)
        cold_ms = (time.perf_counter() - t0) * 1000
        page_cache.put(key, pages)

        t0 = time.perf_counter()
        result = page_cache.get(key)
        warm_ms = (time.perf_counter() - t0) * 1000

        print(
            f"\n  Page cache hit\n"
            f"    cold (parse + paginate) : {cold_ms:.1f} ms\n"
            f"    warm (cache hit)        : {warm_ms:.3f} ms\n"
            f"    speedup                 : {cold_ms / max(warm_ms, 0.001):.0f}×"
        )

        assert result is not None
        assert warm_ms < cold_ms
        page_cache._cache.pop(key, None)
