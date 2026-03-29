"""
Upload server — Flask app definition + lifecycle manager.

The server is started/stopped from the Settings screen on the e-reader.
It is never run as a standalone script.
"""
from __future__ import annotations
import threading
from pathlib import Path

from flask import Flask, request, render_template_string, send_file, Response
from werkzeug.serving import make_server

from core.epub_parser import parse_epub, extract_cover_image
from data.database import (
    init_db, add_book, get_all_books, get_book_by_id,
    update_cover, get_setting, set_setting,
)

from core import fonts as _fonts

PORT = 3003
_UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
_COVERS_DIR = Path(__file__).parent.parent / "data" / "covers"
_UPLOAD_DIR.mkdir(exist_ok=True)
_COVERS_DIR.mkdir(parents=True, exist_ok=True)

FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 32
FONT_SIZE_DEFAULT = 16

_FONT_OPTIONS = [
    (_fonts.COMMIT_MONO, "CommitMono",  "font-mono",  "Monospaced — great for readability"),
    (_fonts.SYSTEM,      "System Sans", "font-sans",  "System sans-serif — clean and light"),
]

# ------------------------------------------------------------------
# Flask app
# ------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

_BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>E-Reader</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-stone-100 text-stone-900 min-h-screen">
  <nav class="bg-white shadow-sm border-b border-stone-200">
    <div class="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
      <span class="font-bold text-lg tracking-tight">📚 E-Reader</span>
      <div class="flex gap-6 text-sm font-medium">
        <a href="/" class="{% if active == 'library' %}text-stone-900 border-b-2 border-stone-900 pb-0.5{% else %}text-stone-500 hover:text-stone-700{% endif %}">Library</a>
        <a href="/settings" class="{% if active == 'settings' %}text-stone-900 border-b-2 border-stone-900 pb-0.5{% else %}text-stone-500 hover:text-stone-700{% endif %}">Settings</a>
      </div>
    </div>
  </nav>
  <main class="max-w-3xl mx-auto px-4 py-8">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
"""

_LIBRARY = _BASE.replace("{% block content %}{% endblock %}", """
  {% if message %}
  <div class="mb-6 px-4 py-3 rounded-lg {% if error %}bg-red-50 text-red-800 border border-red-200{% else %}bg-green-50 text-green-800 border border-green-200{% endif %} text-sm">
    {{ message }}
  </div>
  {% endif %}

  <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6 mb-8">
    <h2 class="font-semibold text-base mb-4">Upload a book</h2>
    <form method="post" enctype="multipart/form-data" class="flex items-center gap-3 flex-wrap">
      <div class="flex-1 min-w-48">
        <div class="cursor-pointer border-2 border-dashed border-stone-300 hover:border-stone-400 rounded-xl px-4 py-3 text-sm text-stone-500 text-center transition-colors"
             onclick="document.getElementById('epub-input').click()">
          <span id="fname">Choose an .epub file\u2026</span>
        </div>
        <input id="epub-input" type="file" name="epub" accept=".epub" required
               style="display:none"
               onchange="document.getElementById('fname').textContent = (this.files && this.files[0]) ? this.files[0].name : 'Choose an .epub file\u2026'">
      </div>
      <button type="submit"
              class="bg-stone-900 text-white text-sm font-medium px-5 py-3 rounded-xl hover:bg-stone-700 transition-colors">
        Upload
      </button>
    </form>
  </div>

  <h2 class="font-semibold text-base mb-4 text-stone-700">
    Library — <span class="font-normal">{{ books|length }} book{{ 's' if books|length != 1 }}</span>
  </h2>

  {% if books %}
  <div class="space-y-3">
    {% for b in books %}
    <div class="bg-white rounded-2xl shadow-sm border border-stone-200 flex overflow-hidden">
      <div class="w-20 shrink-0 bg-stone-100 flex items-center justify-center overflow-hidden">
        {% if b.cover_path %}
        <img src="/cover/{{ b.id }}" alt="cover" class="w-full h-full object-cover">
        {% else %}
        <span class="text-3xl font-bold text-stone-300">{{ b.title[0]|upper }}</span>
        {% endif %}
      </div>
      <div class="px-4 py-3 flex flex-col justify-center min-w-0">
        <p class="font-semibold text-sm leading-snug truncate">{{ b.title }}</p>
        <p class="text-stone-500 text-xs mt-0.5 truncate">{{ b.author }}{% if b.year %} · {{ b.year }}{% endif %}</p>
        {% if b.total_pages %}
        <div class="mt-2 flex items-center gap-2">
          <div class="flex-1 bg-stone-200 rounded-full h-1">
            <div class="bg-stone-700 h-1 rounded-full" style="width: {{ ((b.current_page / b.total_pages) * 100)|int }}%"></div>
          </div>
          <span class="text-stone-400 text-xs shrink-0">{{ b.current_page }}/{{ b.total_pages }}</span>
        </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <p class="text-stone-400 text-sm text-center py-12">No books yet. Upload an EPUB above.</p>
  {% endif %}
""")

_SETTINGS = _BASE.replace("{% block content %}{% endblock %}", """
  {% if message %}
  <div class="mb-6 px-4 py-3 rounded-lg bg-green-50 text-green-800 border border-green-200 text-sm">
    {{ message }}
  </div>
  {% endif %}

  <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
    <h2 class="font-semibold text-base mb-8">Reader settings</h2>
    <form method="post">

      <!-- Font selector -->
      <div class="mb-8">
        <p class="text-sm font-medium text-stone-700 mb-3">Font</p>
        <div class="grid grid-cols-2 gap-3">
          {% for value, label, cls, desc in font_options %}
          <div>
            <input type="radio" id="font-{{ value }}" name="font_name" value="{{ value }}"
                   class="sr-only peer" {% if value == current_font %}checked{% endif %}>
            <label for="font-{{ value }}"
                   class="flex flex-col gap-1 p-4 rounded-xl border-2 cursor-pointer transition-colors
                          border-stone-200 hover:border-stone-400
                          peer-checked:border-stone-900 peer-checked:bg-stone-50">
              <span class="{{ cls }} text-sm font-semibold text-stone-900">{{ label }}</span>
              <span class="text-xs text-stone-400 mt-1 font-sans">{{ desc }}</span>
            </label>
          </div>
          {% endfor %}
        </div>
      </div>

      <!-- Font size slider -->
      <div class="mb-8">
        <p class="text-sm font-medium text-stone-700 mb-4">
          Font size —
          <span id="fs-display" class="font-semibold tabular-nums">{{ current_font_size }}px</span>
        </p>
        <div class="flex items-center gap-4">
          <span class="text-xs text-stone-400 w-5 shrink-0 text-right">{{ font_size_min }}</span>
          <div class="relative flex-1">
            <input type="range"
                   id="font-size-range"
                   name="font_size"
                   min="{{ font_size_min }}" max="{{ font_size_max }}" step="1"
                   value="{{ current_font_size }}"
                   class="w-full h-2 rounded-lg appearance-none cursor-pointer accent-stone-900 bg-stone-200"
                   oninput="
                     document.getElementById('fs-display').textContent = this.value + 'px';
                     document.getElementById('fs-preview').style.fontSize = this.value + 'px';
                   ">
          </div>
          <span class="text-xs text-stone-400 w-5 shrink-0">{{ font_size_max }}</span>
        </div>
        <!-- Live preview -->
        <div class="mt-5 p-4 rounded-xl bg-stone-50 border border-stone-200 overflow-hidden">
          <p class="text-xs text-stone-400 mb-2 font-sans">Preview</p>
          <p id="fs-preview"
             style="font-size: {{ current_font_size }}px; line-height: 1.6;
                    font-family: {{ 'monospace' if current_font == 'commit_mono' else 'sans-serif' }};
                    transition: font-size 0.15s, font-family 0.1s">
            Quidquid latine dictum sit, altum videtur.
          </p>
        </div>
      </div>

      <button type="submit"
              class="bg-stone-900 text-white text-sm font-medium px-6 py-2.5 rounded-xl hover:bg-stone-700 transition-colors">
        Save settings
      </button>
    </form>
  </div>

  <script>
    // Keep preview in sync with font selector
    document.querySelectorAll('input[name="font_name"]').forEach(function(r) {
      r.addEventListener('change', function() {
        document.getElementById('fs-preview').style.fontFamily =
          this.value === 'commit_mono' ? 'monospace' : 'sans-serif';
      });
    });
  </script>
""")


@app.route("/", methods=["GET", "POST"])
def index():
    message, error = None, False
    if request.method == "POST":
        f = request.files.get("epub")
        if f and f.filename.endswith(".epub"):
            dest = _UPLOAD_DIR / f.filename
            f.save(dest)
            try:
                parsed = parse_epub(dest)
                book_id = add_book(parsed.title, parsed.author, str(dest), parsed.year)
                cover_bytes = extract_cover_image(dest)
                if cover_bytes:
                    cover_path = _COVERS_DIR / f"cover_{book_id}.jpg"
                    cover_path.write_bytes(cover_bytes)
                    update_cover(book_id, str(cover_path))
                from core.page_cache import invalidate
                invalidate(book_id)
                message = f'Added "{parsed.title}" by {parsed.author}'
            except Exception as e:
                message = f"Error parsing EPUB: {e}"
                error = True
        else:
            message = "Please select a valid .epub file."
            error = True
    books = get_all_books()
    return render_template_string(_LIBRARY, books=books, message=message, error=error, active="library")


@app.route("/cover/<int:book_id>")
def cover(book_id: int):
    book = get_book_by_id(book_id)
    if book and book.cover_path:
        p = Path(book.cover_path)
        if p.exists():
            return send_file(str(p))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="112" viewBox="0 0 80 112">'
        '<rect width="80" height="112" fill="#e7e5e4"/>'
        '</svg>'
    )
    return Response(svg, mimetype="image/svg+xml")


@app.route("/settings", methods=["GET", "POST"])
def settings():
    message = None
    if request.method == "POST":
        # Font name
        fn = request.form.get("font_name", _fonts.COMMIT_MONO)
        if fn in (_fonts.COMMIT_MONO, _fonts.SYSTEM):
            set_setting("font_name", fn)
        # Font size
        fs = request.form.get("font_size", str(FONT_SIZE_DEFAULT))
        if fs.isdigit() and FONT_SIZE_MIN <= int(fs) <= FONT_SIZE_MAX:
            set_setting("font_size", fs)
        message = "Settings saved."
    current_font      = get_setting("font_name", _fonts.COMMIT_MONO)
    current_font_size = int(get_setting("font_size", str(FONT_SIZE_DEFAULT)))
    return render_template_string(
        _SETTINGS,
        font_options=_FONT_OPTIONS,
        current_font=current_font,
        current_font_size=current_font_size,
        font_size_min=FONT_SIZE_MIN,
        font_size_max=FONT_SIZE_MAX,
        message=message,
        active="settings",
    )


# ------------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------------

_srv = None
_thread: threading.Thread | None = None


def start() -> None:
    global _srv, _thread
    if _srv is not None:
        return
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
