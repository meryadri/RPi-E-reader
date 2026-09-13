"""
Habit checklist web site — tick habits from your phone.

Never run as a standalone script; the dashboard app starts it on a daemon thread
from App.setup, in the same process as the render loop.  That is what lets a tap
here repaint the panel within a second, with no file watching or IPC.

Reachable from any device on the same network at http://<pi-ip>:3004/?t=<token>.
"""
from __future__ import annotations

import json
import threading
from datetime import timedelta

from flask import Flask, Response, redirect, render_template_string, request
from werkzeug.serving import make_server

from display.netinfo import local_ip

from . import config, service, stats, store

PORT = config.PORT

app = Flask(__name__)


_BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Habits</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-stone-100 text-stone-900 min-h-screen">
  <nav class="bg-white shadow-sm border-b border-stone-200">
    <div class="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
      <span class="font-bold text-lg tracking-tight">Habits</span>
      <div class="flex gap-6 text-sm font-medium">
        <a href="/?t={{ token }}" class="{% if active == 'today' %}text-stone-900 border-b-2 border-stone-900 pb-0.5{% else %}text-stone-500 hover:text-stone-700{% endif %}">Today</a>
        <a href="/history?t={{ token }}" class="{% if active == 'history' %}text-stone-900 border-b-2 border-stone-900 pb-0.5{% else %}text-stone-500 hover:text-stone-700{% endif %}">History</a>
      </div>
    </div>
  </nav>
  <main class="max-w-3xl mx-auto px-4 py-8">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
"""

_TODAY = _BASE.replace("{% block content %}{% endblock %}", """
  <div class="flex items-baseline justify-between mb-6">
    <h1 class="text-2xl font-bold">{{ day.strftime('%A, %B %-d') }}</h1>
    <span class="text-lg font-medium text-stone-500">{{ done_count }}/{{ total }}</span>
  </div>

  {% if not habits %}
    <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6">
      <p class="font-medium mb-2">No habits configured yet.</p>
      <p class="text-sm text-stone-600">
        Create <code class="bg-stone-100 px-1 rounded">private/habits.json</code>
        with a list of names, then restart the dashboard.
      </p>
    </div>
  {% else %}
    <div class="bg-white rounded-2xl shadow-sm border border-stone-200 divide-y divide-stone-100 overflow-hidden">
      {% for h in habits %}
      <form method="post" action="/toggle?t={{ token }}">
        <input type="hidden" name="habit" value="{{ h.name }}">
        <button type="submit"
                class="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-stone-50 active:bg-stone-100">
          <span class="shrink-0 w-7 h-7 rounded-lg border-2 flex items-center justify-center
                       {% if h.done %}bg-stone-900 border-stone-900 text-white{% else %}border-stone-300{% endif %}">
            {% if h.done %}&check;{% endif %}
          </span>
          <span class="flex-1 text-lg {% if h.done %}line-through text-stone-400{% endif %}">{{ h.name }}</span>
          {% if h.streak %}
            <span class="text-sm font-medium text-stone-500 tabular-nums">{{ h.streak }}d</span>
          {% endif %}
        </button>
      </form>
      {% endfor %}
    </div>
    {% if weekend %}
    <p class="text-sm text-stone-500 mt-4 bg-white border border-stone-200 rounded-xl px-4 py-3">
      It&rsquo;s the weekend &mdash; today counts neither for nor against your
      streaks. Anything you tick is a bonus.
    </p>
    {% endif %}
    <p class="text-xs text-stone-400 mt-4">
      The day rolls over at {{ rollover }}:00, so a late-night tick still counts for the day before.
    </p>
  {% endif %}
""")

_HISTORY = _BASE.replace("{% block content %}{% endblock %}", """
  <div class="flex items-baseline justify-between mb-6">
    <h1 class="text-2xl font-bold">Consistency</h1>
    <a href="/export?t={{ token }}"
       class="text-sm font-medium bg-stone-900 text-white px-3 py-1.5 rounded-lg">Download backup</a>
  </div>

  {% if not rows %}
    <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-6 text-stone-600">
      No habits configured yet.
    </div>
  {% else %}
  <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-5 mb-6">
    <p class="text-xs text-stone-400 mb-4">
      Each block is a calendar month; columns run Monday to Sunday.
      Weekends never count for or against a streak &mdash; a missed Saturday
      leaves a run intact, and a completed one is a bonus (shown lighter).
    </p>
    {% for r in rows %}
    <div class="mb-6 last:mb-0">
      <div class="flex items-baseline justify-between mb-2">
        <span class="font-medium">{{ r.name }}</span>
        <span class="text-sm text-stone-500">
          <span class="font-semibold text-stone-900">{{ r.streak }}d</span> now
          &middot; best {{ r.best }}d
        </span>
      </div>
      <div class="flex flex-wrap gap-x-3 gap-y-2">
        {% for m in r.months %}
        <div>
          <div class="text-[10px] font-medium text-stone-400 mb-1 text-center tracking-wide">{{ m.label }}</div>
          <div class="grid grid-cols-7 gap-px">
            {% for c in m.cells %}
              {% if c.state == 'pad' %}
                <span class="w-2.5 h-2.5"></span>
              {% elif c.state == 'future' %}
                <span class="w-2.5 h-2.5 rounded-[2px] border border-stone-100"></span>
              {% elif c.state == 'done' %}
                {# Weekend wins are drawn lighter: they are a bonus, not part of the streak. #}
                <span title="{{ c.day }}"
                      class="w-2.5 h-2.5 rounded-[2px] {% if c.weekend %}bg-stone-400{% else %}bg-stone-900{% endif %}"></span>
              {% elif c.weekend %}
                {# A missed weekend is not a miss at all. #}
                <span title="{{ c.day }}" class="w-2.5 h-2.5 rounded-[2px] bg-stone-50"></span>
              {% else %}
                <span title="{{ c.day }}" class="w-2.5 h-2.5 rounded-[2px] bg-stone-200"></span>
              {% endif %}
            {% endfor %}
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </div>

  <div class="bg-white rounded-2xl shadow-sm border border-stone-200 p-5">
    <table class="w-full text-sm">
      <thead class="text-stone-400 text-xs">
        <tr><th class="text-left font-medium pb-2">Habit</th>
            <th class="text-right font-medium pb-2 w-16">7d</th>
            <th class="text-right font-medium pb-2 w-16">30d</th>
            <th class="text-right font-medium pb-2 w-16">90d</th></tr>
      </thead>
      <tbody class="divide-y divide-stone-100">
        {% for r in rows %}
        <tr><td class="py-2">{{ r.name }}</td>
            <td class="py-2 text-right tabular-nums">{{ r.d7 }}%</td>
            <td class="py-2 text-right tabular-nums">{{ r.d30 }}%</td>
            <td class="py-2 text-right tabular-nums">{{ r.d90 }}%</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
""")


def _authorised() -> bool:
    """The token keeps habit names off a casual scan of the home network.

    Not authentication — anyone who sees the URL has access.  See
    private/README.md.
    """
    return request.args.get("t") == store.load_token()


@app.route("/")
def index():
    if not _authorised():
        return Response("Not found", status=404)

    snap = service.get_snapshot()
    day = config.habit_day()
    rows = [
        {"name": h, "done": h in snap.done, "streak": snap.streaks.get(h, 0)}
        for h in snap.habits
    ]
    done_count, total = snap.progress()
    return render_template_string(
        _TODAY, habits=rows, day=day, done_count=done_count, total=total,
        token=store.load_token(), rollover=config.ROLLOVER_HOUR,
        weekend=not stats.is_workday(day), active="today",
    )


@app.route("/toggle", methods=["POST"])
def toggle():
    if not _authorised():
        return Response("Not found", status=404)
    habit = request.form.get("habit", "")
    if habit:
        service.toggle(habit)
    return redirect(f"/?t={store.load_token()}")


@app.route("/history")
def history():
    if not _authorised():
        return Response("Not found", status=404)

    snap = service.get_snapshot()
    log = service.get_log()
    today = config.habit_day()
    months = config.HEATMAP_MONTHS

    rows = [{
        "name": h,
        "streak": stats.current_streak(log, h, today),
        "best": stats.longest_streak(log, h),
        "months": stats.month_grid(log, h, today, months),
        "d7": round(stats.completion_rate(log, h, today, 7) * 100),
        "d30": round(stats.completion_rate(log, h, today, 30) * 100),
        "d90": round(stats.completion_rate(log, h, today, 90) * 100),
    } for h in snap.habits]

    return render_template_string(
        _HISTORY, rows=rows, token=store.load_token(), active="history",
    )


@app.route("/export")
def export():
    if not _authorised():
        return Response("Not found", status=404)
    body = json.dumps(service.get_log(), indent=1, sort_keys=True)
    return Response(
        body, mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=habit_log.json"},
    )


# ---------------------------------------------------------------------------
# Lifecycle — mirrors apps/ereader/server.py
# ---------------------------------------------------------------------------

_srv = None
_thread: threading.Thread | None = None


def url() -> str:
    return f"http://{local_ip()}:{PORT}/?t={store.load_token()}"


def start() -> None:
    global _srv, _thread
    if _srv is not None:
        return
    # make_server rather than app.run(), so the render loop keeps the main
    # thread and the server can be shut down cleanly.
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
