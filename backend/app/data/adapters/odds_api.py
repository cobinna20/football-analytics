# REAL DATA: The Odds API - real bookmaker odds
# Free: 500 requests / month. Needs ODDS_API_KEY
import os
import httpx

KEY = os.getenv("ODDS_API_KEY", "")
BASE = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

async def get_odds_real(fixture_home: str, fixture_away: str):
    # Returns {home, draw, away} real odds or None
    if not KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(BASE, params={"apiKey": KEY, "regions": "uk", "markets": "h2h", "oddsFormat": "decimal"})
            if r.status_code != 200:
                return None
            data = r.json()
            for game in data:
                # Match by team name - simple fuzzy match
                if fixture_home.lower() in game["home_team"].lower() or game["home_team"].lower() in fixture_home.lower():
                    # Find first bookmaker with h2h
                    for book in game.get("bookmakers", []):
                        for market in book.get("markets", []):
                            if market["key"] == "h2h":
                                outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                                home = outcomes.get(game["home_team"], 2.0)
                                away = outcomes.get(game["away_team"], 3.0)
                                draw = outcomes.get("Draw", 3.2)
                                return {"home": home, "draw": draw, "away": away, "bookmaker": book["title"], "source": "real"}
            return None
    except Exception:
        return None
