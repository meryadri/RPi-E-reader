"""
Flask upload server.
Run independently: python upload_server.py
Accessible at http://<device-ip>:3003
"""
from pathlib import Path
from flask import Flask, request, redirect, url_for, render_template_string
from core.epub_parser import parse_epub
from data.database import init_db, add_book, get_all_books

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

HTML = """
<!doctype html>
<html>
<head>
  <title>E-Reader Upload</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; }
    h1   { font-size: 1.4rem; }
    input[type=file] { margin: 16px 0; }
    button { padding: 10px 24px; font-size: 1rem; cursor: pointer; }
    ul { list-style: none; padding: 0; }
    li { padding: 8px 0; border-bottom: 1px solid #eee; }
    .author { color: #666; font-size: 0.9rem; }
    {% if message %}.msg { padding: 10px; background: #e8f5e9; border-radius: 4px; }{% endif %}
  </style>
</head>
<body>
  <h1>E-Reader Book Upload</h1>
  {% if message %}<p class="msg">{{ message }}</p>{% endif %}
  <form method="post" enctype="multipart/form-data">
    <input type="file" name="epub" accept=".epub" required>
    <br>
    <button type="submit">Upload</button>
  </form>
  <h2>Library ({{ books|length }} books)</h2>
  <ul>
    {% for b in books %}
    <li>
      <strong>{{ b.title }}</strong><br>
      <span class="author">{{ b.author }}</span>
    </li>
    {% endfor %}
  </ul>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    message = None
    if request.method == "POST":
        f = request.files.get("epub")
        if f and f.filename.endswith(".epub"):
            dest = UPLOAD_DIR / f.filename
            f.save(dest)
            try:
                parsed = parse_epub(dest)
                add_book(parsed.title, parsed.author, str(dest))
                message = f'Added "{parsed.title}" by {parsed.author}'
            except Exception as e:
                message = f"Error parsing EPUB: {e}"
        else:
            message = "Please select a valid .epub file."
    books = get_all_books()
    return render_template_string(HTML, books=books, message=message)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=3003, debug=True)
