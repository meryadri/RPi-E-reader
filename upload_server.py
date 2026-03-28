"""
Flask upload server.
Run standalone: python upload_server.py
Or started/stopped from the e-reader settings screen via core.server_manager.

Stack: Flask + Tailwind CSS (CDN) — no extra Python deps, clean modern UI.
"""
from pathlib import Path
from flask import Flask, request, render_template_string, send_file, Response
from core.epub_parser import parse_epub, extract_cover_image
from data.database import (
    init_db, add_book, get_all_books, get_book_by_id,
    update_cover, get_setting, set_setting,
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
COVERS_DIR = Path(__file__).parent / "data" / "covers"
UPLOAD_DIR.mkdir(exist_ok=True)
COVERS_DIR.mkdir(parents=True, exist_ok=True)

FONT_SIZE_OPTIONS = [18, 20, 22, 24, 26, 28]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# ------------------------------------------------------------------
# Templates
# ------------------------------------------------------------------

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

  <!-- Upload card -->
  <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6 mb-8">
    <h2 class="font-semibold text-base mb-4">Upload a book</h2>
    <form method="post" enctype="multipart/form-data" class="flex items-center gap-3 flex-wrap">
      <label class="flex-1 min-w-48 cursor-pointer">
        <div class="border-2 border-dashed border-stone-300 hover:border-stone-400 rounded-xl px-4 py-3 text-sm text-stone-500 text-center transition-colors">
          <span id="fname">Choose an .epub file…</span>
          <input type="file" name="epub" accept=".epub" required class="hidden"
                 onchange="document.getElementById('fname').textContent = this.files[0]?.name || 'Choose an .epub file…'">
        </div>
      </label>
      <button type="submit"
              class="bg-stone-900 text-white text-sm font-medium px-5 py-3 rounded-xl hover:bg-stone-700 transition-colors">
        Upload
      </button>
    </form>
  </div>

  <!-- Book list -->
  <h2 class="font-semibold text-base mb-4 text-stone-700">
    Library — <span class="font-normal">{{ books|length }} book{{ 's' if books|length != 1 }}</span>
  </h2>

  {% if books %}
  <div class="space-y-3">
    {% for b in books %}
    <div class="bg-white rounded-2xl shadow-sm border border-stone-200 flex overflow-hidden">
      <!-- Cover -->
      <div class="w-20 shrink-0 bg-stone-100 flex items-center justify-center overflow-hidden">
        {% if b.cover_path %}
        <img src="/cover/{{ b.id }}" alt="cover" class="w-full h-full object-cover">
        {% else %}
        <span class="text-3xl font-bold text-stone-300">{{ b.title[0]|upper }}</span>
        {% endif %}
      </div>
      <!-- Meta -->
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
    <h2 class="font-semibold text-base mb-6">Reader settings</h2>
    <form method="post">

      <div class="mb-6">
        <label class="block text-sm font-medium text-stone-700 mb-3">Font size</label>
        <div class="flex flex-wrap gap-2">
          {% for size in font_sizes %}
          <label class="cursor-pointer">
            <input type="radio" name="font_size" value="{{ size }}" class="sr-only peer"
                   {% if size == current_font_size %}checked{% endif %}>
            <span class="px-4 py-2 rounded-xl border text-sm font-medium transition-colors
                         border-stone-200 text-stone-600
                         peer-checked:bg-stone-900 peer-checked:text-white peer-checked:border-stone-900
                         hover:border-stone-400">
              {{ size }}px
            </span>
          </label>
          {% endfor %}
        </div>
      </div>

      <button type="submit"
              class="bg-stone-900 text-white text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-stone-700 transition-colors">
        Save settings
      </button>
    </form>
  </div>
""")


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    message, error = None, False
    if request.method == "POST":
        f = request.files.get("epub")
        if f and f.filename.endswith(".epub"):
            dest = UPLOAD_DIR / f.filename
            f.save(dest)
            try:
                parsed = parse_epub(dest)
                book_id = add_book(parsed.title, parsed.author, str(dest), parsed.year)
                # Save cover image
                cover_bytes = extract_cover_image(dest)
                if cover_bytes:
                    cover_path = COVERS_DIR / f"cover_{book_id}.jpg"
                    cover_path.write_bytes(cover_bytes)
                    update_cover(book_id, str(cover_path))
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
    # Minimal SVG placeholder
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
        fs = request.form.get("font_size", "22")
        if fs.isdigit() and int(fs) in FONT_SIZE_OPTIONS:
            set_setting("font_size", fs)
            message = "Settings saved."
    current_font_size = int(get_setting("font_size", "22"))
    return render_template_string(
        _SETTINGS,
        font_sizes=FONT_SIZE_OPTIONS,
        current_font_size=current_font_size,
        message=message,
        active="settings",
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=3003, debug=True)
