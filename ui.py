"""
Challenge 3 - User Interface.

Lightweight local UI (Flask) that presents the results from Challenges 1 and 2:

  * ``/``            - dashboard: today's/tomorrow's races (df_races_data)
  * ``/races``       - races table
  * ``/bets``        - performed bets / market prices (df_performed_bets)
  * ``/refresh``     - re-run Challenge 1 scraper (regenerates df_races_data.csv)

Run locally:
    python3 ui.py
then open http://127.0.0.1:5000
"""

from __future__ import annotations

import os

import pandas as pd
from flask import Flask, redirect, render_template_string, request, url_for

from config import BETS_CSV, DATA_DIR, RACES_CSV
from scraper import SwiftbetAuthError, scrape_races

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template (inline, keeps the UI self-contained and lightweight)
# ---------------------------------------------------------------------------
PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>White Swan Data Assignment &mdash; Swiftbet Racing</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         margin: 0; background: #f4f5f7; color: #1a1a1a; }
  header { background: #0b3d62; color: #fff; padding: 1rem 1.5rem; }
  header h1 { margin: 0; font-size: 1.25rem; letter-spacing: 0.5px; }
  header p { margin: 0.25rem 0 0; font-size: 0.85rem; color: #c8d6e4; }
  .container { max-width: 1100px; margin: 1.5rem auto; padding: 0 1rem; }
  nav { margin-bottom: 1rem; }
  nav a { display: inline-block; padding: 0.5rem 0.9rem; margin-right: 0.5rem;
          background: #fff; color: #0b3d62; text-decoration: none;
          border-radius: 6px; font-weight: 600; font-size: 0.9rem;
          border: 1px solid #d1d5db; }
  nav a:hover { background: #eef2f7; }
  .btn-refresh { background: #0b3d62; color: #fff; border-color: #0b3d62; }
  .btn-refresh:hover { background: #093454; }
  .card { background: #fff; border: 1px solid #d1d5db; border-radius: 8px;
          padding: 1rem; margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
  .card h2 { margin: 0 0 0.75rem; font-size: 1rem; text-transform: uppercase;
             letter-spacing: 0.6px; color: #0b3d62; border-bottom: 2px solid #eef2f7;
             padding-bottom: 0.4rem; }
  .muted { color: #6b7280; font-size: 0.85rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #eef2f7; }
  th { background: #f8f9fa; font-weight: 700; color: #374151; position: sticky; top: 0; }
  tr:nth-child(even) td { background: #fafbfc; }
  tr:hover td { background: #f0f4f8; }
  .empty { padding: 1.5rem; color: #6b7280; text-align: center; }
  .badge { display: inline-block; padding: 0.12rem 0.5rem; border-radius: 999px;
           font-size: 0.75rem; font-weight: 700; background: #eef2f7; color: #0b3d62; }
</style>
</head>
<body>
<header>
  <h1>White Swan Data Assignment &mdash; Swiftbet Racing</h1>
  <p>Challenge 1: races &bull; Challenge 2: performed bets &bull; Challenge 3: this UI</p>
</header>
<div class="container">
  <nav>
    <a href="{{ url_for('races') }}">Races (df_races_data)</a>
    <a href="{{ url_for('bets') }}">Performed Bets (df_performed_bets)</a>
    <a class="btn-refresh" href="{{ url_for('refresh') }}">Refresh Races</a>
  </nav>

  {{ content | safe }}

  <div class="card muted" style="font-size:0.8rem;">
    <strong>Notes:</strong> Live data is fetched from the Swiftbet racing GraphQL endpoint
    (AppSync). It requires an AppSync API key via the <code>SWIFTBET_APPSYNC_API_KEY</code>
    environment variable (or a <code>.env</code> file). Without credentials the scraper
    reports a clear auth error instead of failing silently.
  </div>
</div>
</body>
</html>
"""


def _read_csv(path):
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _df_html(df, title):
    if df is None or df.empty:
        return f"""
        <div class="card"><h2>{title}</h2>
        <div class="empty">No data available.</div></div>"""
    # Show a safe, relevant subset of columns for readability.
    bet_cols = ("horse_name", "runner_id", "tab_no", "market_price", "market_type")
    race_cols = ("meeting_date", "track_name", "race_number", "race_time",
                 "minutes_to_start", "race_status", "race_url")
    preferred = bet_cols if any(c in df.columns for c in bet_cols) else race_cols
    show_cols = [c for c in df.columns if c in preferred] or list(df.columns[:8])
    html = df[show_cols].to_html(index=False, classes="", border=0)
    return f"""
    <div class="card">
      <h2>{title} <span class="badge">{len(df)} rows</span></h2>
      {html}
      <p class="muted">Source: <code>{'data/df_races_data.csv' if 'df_races_data' in title else 'data/df_performed_bets.csv'}</code></p>
    </div>"""


@app.route("/")
def index():
    return redirect(url_for("races"))


@app.route("/races")
def races():
    df = _read_csv(RACES_CSV)
    content = _df_html(df, "Races &mdash; df_races_data") if df is not None else """
    <div class="card"><h2>Races &mdash; df_races_data</h2>
    <div class="empty">
      No races data yet. Run Challenge 1 first: <code>python3 -m scraper</code> (live)
      or provide a <code>data/df_races_data.csv</code> file.
    </div></div>"""
    return render_template_string(PAGE, content=content)


@app.route("/bets")
def bets():
    df = _read_csv(BETS_CSV)
    content = _df_html(df, "Performed Bets &mdash; df_performed_bets") if df is not None else """
    <div class="card"><h2>Performed Bets &mdash; df_performed_bets</h2>
    <div class="empty">
      No performed-bets data yet. Run Challenge 2 first:
      <code>python3 -m bot</code> (requires a races CSV + live credentials).
    </div></div>"""
    return render_template_string(PAGE, content=content)


@app.route("/refresh", methods=["GET", "POST"])
def refresh():
    """Re-run Challenge 1 to regenerate df_races_data.csv."""
    error = None
    df = None
    try:
        df = scrape_races()
    except SwiftbetAuthError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"Refresh failed: {exc}"
    if df is not None:
        content = f"""
        <div class="card"><h2>Refresh &mdash; df_races_data</h2>
        <p style="color:#15803d;">&#10003; Refreshed successfully &mdash; {len(df)} races scraped.</p>
        <p><a href="{{ url_for('races') }}">View races</a></p></div>"""
    else:
        content = f"""
        <div class="card"><h2>Refresh &mdash; df_races_data</h2>
        <div class="empty" style="color:#b91c1c;">
          Refresh failed: {error}
        </div>
        <p><a href="{{ url_for('races') }}">Back to races</a></p></div>"""
    return render_template_string(PAGE, content=content)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
