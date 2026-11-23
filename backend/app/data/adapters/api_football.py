import os
import requests
from datetime import date, timedelta

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

def _parse_date(s: str):
    try:
        y, m, d = map(int, s[:10].split("-"))
        return date(y, m, d)
    except Exception:
        return date.today()

def _chunks(start: date, end: date, days: int = 7):
    # API-Football rejects ranges >7 days, so split 14 days into 2x 7-day calls
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days-1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)

def get_fixtures(start_date: str, end_date: str):
    # FIX: Load key INSIDE function, not at top, so Render env var is picked up
    API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
    print(f"[api_football] key present={bool(API_KEY)} len={len(API_KEY)} range={start_date} to {end_date}", flush=True)
    if not API_KEY:
        print("[api_football] NO KEY - returning empty", flush=True)
        return []

    all_fixtures = []
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    headers = {"x-apisports-key": API_KEY}

    for league_id, league_name in NEW_LEAGUES.items():
        try:
            for c_start, c_end in _chunks(start, end, 7):
                params = {
                    "league": league_id,
                    "season": 2026,
                    "from": c_start.isoformat(),
                    "to": c_end.isoformat(),
                    "timezone": "Europe/London",
                }
                r = requests.get(f"{BASE}/fixtures", headers=headers, params=params, timeout=15)
                print(f"[api_football] {league_name} {c_start} to {c_end} status={r.status_code}", flush=True)
                if r.status_code != 200:
                    print(f"[api_football] {league_name} error: {r.text[:200]}", flush=True)
                    continue
                data = r.json()
                # Log API errors like rate limit
                if data.get("errors"):
                    print(f"[api_football] {league_name} api errors: {data.get('errors')}", flush=True)
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
        except Exception as e:
            print(f"[api_football] {league_name} exception: {e}", flush=True)
            continue

    print(f"[api_football] total returned: {len(all_fixtures)}", flush=True)
    return all_fixtures
