"""
Betting Tips Aggregator — prototype
------------------------------------
Pulls live odds from The Odds API and tips from RSS-based tipster sources,
normalizes them into one structure, scores each source by historical
accuracy, and prints/stores a ranked feed.

Setup:
    pip install requests feedparser --break-system-packages

    Get a free API key from https://the-odds-api.com (500 req/month free)
    export ODDS_API_KEY="your_key_here"

Run:
    python3 aggregator.py
"""

import os
import sqlite3
import requests
import feedparser
from datetime import datetime, timezone

DB_PATH = "tips.db"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Add/remove RSS-friendly tipster sources here.
# Many tipster sites don't offer RSS — check each site's ToS before adding.
RSS_SOURCES = [
    {"name": "Forebet", "url": "https://www.forebet.com/en/rss/predictions-1x2"},
    # add more RSS feeds here as you find them
]

SPORTS_TO_TRACK = ["soccer_fifa_world_cup", "soccer_epl"]


# ---------- storage ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            match_name TEXT,
            market TEXT,
            pick TEXT,
            odds REAL,
            confidence REAL,
            fetched_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_accuracy (
            source TEXT PRIMARY KEY,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def save_tip(conn, source, match_name, market, pick, odds, confidence):
    conn.execute(
        "INSERT INTO tips (source, match_name, market, pick, odds, confidence, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source, match_name, market, pick, odds, confidence,
         datetime.now(timezone.utc).isoformat())
    )
    conn.commit()


def source_weight(conn, source):
    row = conn.execute(
        "SELECT wins, losses FROM source_accuracy WHERE source=?", (source,)
    ).fetchone()
    if not row or (row[0] + row[1]) == 0:
        return 0.5  # neutral weight until we have a track record
    wins, losses = row
    return wins / (wins + losses)


# ---------- fetchers ----------

def fetch_odds_api(conn):
    """Pull live odds for tracked sports and derive a 'tip' = the favourite."""
    if not ODDS_API_KEY:
        print("No ODDS_API_KEY set — skipping live odds fetch.")
        return

    for sport in SPORTS_TO_TRACK:
        url = f"{ODDS_API_BASE}/sports/{sport}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "uk,eu,au",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            games = resp.json()
        except Exception as e:
            print(f"Odds API error for {sport}: {e}")
            continue

        for game in games:
            home, away = game.get("home_team"), game.get("away_team")
            match_name = f"{home} vs {away}"
            # average odds across bookmakers, pick the shortest price as the "tip"
            outcome_prices = {}
            for bk in game.get("bookmakers", []):
                for market in bk.get("markets", []):
                    if market["key"] != "h2h":
                        continue
                    for outcome in market["outcomes"]:
                        outcome_prices.setdefault(outcome["name"], []).append(outcome["price"])

            if not outcome_prices:
                continue

            avg_prices = {k: sum(v) / len(v) for k, v in outcome_prices.items()}
            favourite = min(avg_prices, key=avg_prices.get)
            implied_prob = 1 / avg_prices[favourite]

            save_tip(conn, "OddsAPI-Favourite", match_name, "Match Winner",
                     favourite, round(avg_prices[favourite], 2), round(implied_prob * 100, 1))


def fetch_rss_tips(conn):
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
        except Exception as e:
            print(f"RSS error for {src['name']}: {e}")
            continue

        for entry in feed.entries[:15]:
            save_tip(conn, src["name"], entry.get("title", "Unknown match"),
                     "RSS Tip", entry.get("summary", "")[:120], None, None)


# ---------- ranking / output ----------

def print_ranked_feed(conn, limit=10):
    rows = conn.execute(
        "SELECT source, match_name, market, pick, odds, confidence FROM tips "
        "ORDER BY fetched_at DESC LIMIT 200"
    ).fetchall()

    ranked = []
    for source, match_name, market, pick, odds, confidence in rows:
        weight = source_weight(conn, source)
        score = (confidence or 50) * weight
        ranked.append((score, source, match_name, market, pick, odds, confidence))

    ranked.sort(reverse=True, key=lambda r: r[0])

    print("\n=== TOP TIPS (ranked by source track record x confidence) ===\n")
    for score, source, match_name, market, pick, odds, confidence in ranked[:limit]:
        odds_str = f" @ {odds}" if odds else ""
        conf_str = f" ({confidence}% confidence)" if confidence else ""
        print(f"[{source}] {match_name} — {market}: {pick}{odds_str}{conf_str}  | score={score:.1f}")


def record_result(conn, source, won: bool):
    """Call this after a tip resolves to build up source accuracy over time."""
    conn.execute(
        "INSERT INTO source_accuracy (source, wins, losses) VALUES (?, ?, ?) "
        "ON CONFLICT(source) DO UPDATE SET "
        "wins = wins + excluded.wins, losses = losses + excluded.losses",
        (source, 1 if won else 0, 0 if won else 1)
    )
    conn.commit()


if __name__ == "__main__":
    conn = init_db()
    fetch_odds_api(conn)
    fetch_rss_tips(conn)
    print_ranked_feed(conn)
    conn.close()
