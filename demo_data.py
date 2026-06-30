"""Adds sample tips so the app is usable immediately, before you set up a real API key."""

DEMO_TIPS = [
    ("OddsAPI-Favourite", "France vs Sweden", "Match Winner", "France", 1.32, 75.0),
    ("OddsAPI-Favourite", "Spain vs Austria", "Match Winner", "Spain", 1.38, 72.5),
    ("OddsAPI-Favourite", "England vs Congo DR", "Match Winner", "England", 1.31, 76.5),
    ("OddsAPI-Favourite", "USA vs Bosnia", "Match Winner", "USA", 1.43, 69.9),
    ("OddsAPI-Favourite", "Portugal vs Croatia", "Match Winner", "Portugal", 1.87, 53.5),
    ("OddsAPI-Favourite", "Belgium vs Senegal", "Match Winner", "Belgium", 2.29, 43.6),
]


def seed_demo_data(conn):
    import aggregator
    for source, match_name, market, pick, odds, confidence in DEMO_TIPS:
        aggregator.save_tip(conn, source, match_name, market, pick, odds, confidence)
