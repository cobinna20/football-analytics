# REAL DATA: Football-Data.org - fixtures, teams, scores
# Free: 10 requests / minute. Needs FOOTBALL_DATA_API_KEY
import os
import httpx

BASE = "https://api.football-data.org/v4"
KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
HEADERS = {"X-Auth-Token": KEY}

async def get_teams_real():
    if not KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{BASE}/competitions/PL/teams", headers=HEADERS)
            if r.status_code != 200:
                return None
            data = r.json()
            teams = []
            for t in data.get("teams", []):
                teams.append({
                    "id": str(t["id"]),
                    "name": t["name"],
                    "short_name": t.get("shortName", t["name"][:3].upper()),
                    "crest": t.get("crest", ""),
                    "venue": t.get("venue", ""),
                })
            return teams
    except Exception:
        return None

async def get_fixtures_real():
    if not KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Next 10 scheduled + last 5 finished = real form
            r = await client.get(f"{BASE}/competitions/PL/matches?status=SCHEDULED,FINISHED&limit=20", headers=HEADERS)
            if r.status_code != 200:
                return None
            data = r.json()
            fixtures = []
            for m in data.get("matches", []):
                fixtures.append({
                    "id": str(m["id"]),
                    "home_team": {"id": str(m["homeTeam"]["id"]), "name": m["homeTeam"]["name"], "short_name": m["homeTeam"].get("shortName", m["homeTeam"]["name"][:3].upper())},
                    "away_team": {"id": str(m["awayTeam"]["id"]), "name": m["awayTeam"]["name"], "short_name": m["awayTeam"].get("shortName", m["awayTeam"]["name"][:3].upper())},
                    "date": m["utcDate"],
                    "status": m["status"],
                    "home_score": m["score"]["fullTime"]["home"],
                    "away_score": m["score"]["fullTime"]["away"],
                    "competition": "PL",
                })
            return fixtures
    except Exception:
        return None

async def get_team_recent_goals_real(team_id: str):
    # Use real finished matches to build real stats when xG API is not available
    if not KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{BASE}/teams/{team_id}/matches?status=FINISHED&limit=8", headers=HEADERS)
            if r.status_code != 200:
                return None
            return r.json().get("matches", [])
    except Exception:
        return None
