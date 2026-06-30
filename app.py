"""
Betting Tips App — run this and open it on your phone.
---------------------------------------------------------
Start it:
    python3 app.py

Then on your Android phone, open Chrome and go to:
    http://<your-computer's-IP>:5000

Tap the Chrome menu (⋮) → "Add to Home screen" — it'll behave just like
a normal app icon from then on.

If you don't have ODDS_API_KEY set, the app shows demo data so you can
see exactly how it'll look once it's live.
"""

import os
import sqlite3
from flask import Flask, render_template, redirect, url_for

import aggregator
from demo_data import seed_demo_data

app = Flask(__name__)
aggregator.init_db().close()


def get_conn():
    return sqlite3.connect(aggregator.DB_PATH)


@app.route("/")
def home():
    conn = get_conn()

    # If the DB is empty (first run), seed it with demo data so the page
    # isn't blank.
    count = conn.execute("SELECT COUNT(*) FROM tips").fetchone()[0]
    if count == 0:
        seed_demo_data(conn)

    rows = conn.execute(
        "SELECT source, match_name, market, pick, odds, confidence FROM tips "
        "ORDER BY fetched_at DESC LIMIT 200"
    ).fetchall()

    ranked = []
    for source, match_name, market, pick, odds, confidence in rows:
        weight = aggregator.source_weight(conn, source)
        score = (confidence or 50) * weight
        ranked.append({
            "score": score, "source": source, "match": match_name,
            "market": market, "pick": pick, "odds": odds, "confidence": confidence
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)

    has_real_key = bool(os.environ.get("ODDS_API_KEY"))
    conn.close()
    return render_template("index.html", tips=ranked, has_real_key=has_real_key)


@app.route("/refresh")
def refresh():
    conn = get_conn()
    aggregator.fetch_odds_api(conn)
    aggregator.fetch_rss_tips(conn)
    conn.close()
    return redirect(url_for("home"))


@app.route("/init")
def init():
    init_conn = aggregator.init_db()
    init_conn.close()
    return redirect(url_for("home"))


if __name__ == "__main__":
    aggregator.init_db().close()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
