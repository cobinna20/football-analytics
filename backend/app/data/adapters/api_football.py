import os
import requests

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"

# 17 leagues here + 8 old leagues in football_data.py = 25 total
NEW_LEAGUES = {
    40: "Championship",
    144: "Belgian Pro League",
    203: "Turkish Super Lig",
    179: "Scottish Premiership",
    307: "Saudi Pro League",
    253: "MLS",
    71: "Brazil Serie A",
    128: "Argentina Primera",
    3: "Europa League",
    848: "Conference League",
    136: "Serie B Italy",
    141: "La Liga 2 Spain",
    99: "Bundesliga 2 Germany",
    101: "Ligue 2 France",
    262: "Liga MX Mexico",
    98: "J1 League Japan",
    292: "K League 1 Korea",
}

def _headers():
    return {"x-apisports-key": API_KEY}

def get_fixtures(start_date: str, end_date: str):
    if not API_KEY:
        return []
    all_fixtures = []
    for league_id, league_name in NEW_LEAGUES.items():
        try:
            url = f"{BASE}/fixtures"
            params = {
                "league": league_id,
                "season": 2026,
                "from": start_date,
                "to": end_date,
                "timezone": "Europe/London",
            }
            r = requests.get(url, headers=_headers(), params=params, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            for item in data.get("response", []):
                fixture = item.get("fixture", {})
                teams = item.get("teams", {})
                goals = item.get("goals", {})
                status = fixture.get("status", {}).get("short", "NS")
                if status in ["FT", "AET", "PEN"]:
                    match_status = "FINISHED"
                elif status in ["1H", "2H", "HT", "ET", "BT", "P"]:
                    match_status = "LIVE"
                else:
                    match_status = "SCHEDULED"
                all_fixtures.append({
                    "id": f"af-{fixture.get('id')}",
                    "date": fixture.get("date", "")[:10],
                    "time": fixture.get("date", "")[11:16],
                    "home_team": teams.get("home", {}).get("name", "Home"),
                    "away_team": teams.get("away", {}).get("name", "Away"),
                    "home_score": goals.get("home"),
                    "away_score": goals.get("away"),
                    "status": match_status,
                    "league": league_name,
                    "league_code": f"AF-{league_id}",
                })
        except Exception:
            continue
    return all_fixtures
