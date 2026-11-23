# REAL DATA: Football-Data.org - 22 leagues, date range, played + upcoming
# FIX: Use single /matches call for ALL leagues (1 request, not 22)
# so we stay under Football-Data 10 req/min limit
import os
import asyncio
import httpx
from datetime import date, timedelta

BASE = "https://api.football-data.org/v4"
KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
HEADERS = {"X-Auth-Token": KEY}

LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "CL": "Champions League",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "ELC": "Championship",
    "EL": "Europa League",
    "ECL": "Conference League",
    "SB": "Serie B Italy",
    "SD": "La Liga 2 Spain",
    "BL2": "Bundesliga 2",
    "FL2": "Ligue 2 France",
    "BPL": "Belgian Pro League",
    "BSA": "Brazil Serie A",
    "MLS": "MLS",
    "SP": "Scottish Premiership",
    "APD": "Argentina Primera",
    "TSL": "Turkish Super Lig",
    "SPL": "Saudi Pro League",
}

def default_range():
    today = date.today()
    return (today - timedelta(days=7)).isoformat(), (today + timedelta(days=7)).isoformat()

def _format_match(m, code):
    return {
        "id": str(m["id"]),
        "home_team": {"id": str(m["homeTeam"]["id"]), "name": m["homeTeam"]["name"], "short_name": m["homeTeam"].get("shortName", m["homeTeam"]["name"][:3].upper())},
        "away_team": {"id": str(m["awayTeam"]["id"]), "name": m["awayTeam"]["name"], "short_name": m["awayTeam"].get("shortName", m["awayTeam"]["name"][:3].upper())},
        "date": m["utcDate"],
        "status": m["status"],
        "home_score": m["score"]["fullTime"]["home"],
        "away_score": m["score"]["fullTime"]["away"],
        "competition": code,
        "league_code": code,
        "league_name": LEAGUES.get(code, code),
    }

async def _fetch_league(code: str, date_from: str, date_to: str):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{BASE}/competitions/{code}/matches", params={"dateFrom": date_from, "dateTo": date_to}, headers=HEADERS)
            if r.status_code != 200:
                return []
            data = r.json()
            out = []
            for m in data.get("matches", []):
                out.append(_format_match(m, code))
            return out
    except Exception:
        return []

async def get_fixtures_real(competition: str = "ALL", date_from: str | None = None, date_to: str | None = None):
    if not KEY:
        return None
    if not date_from or not date_to:
        date_from, date_to = default_range()
    if competition and competition != "ALL":
        res = await _fetch_league(competition, date_from, date_to)
        return res if res else None

    # ALL leagues - try single /matches call first (1 request for all leagues)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{BASE}/matches", params={"dateFrom": date_from, "dateTo": date_to}, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                out = []
                for m in data.get("matches", []):
                    comp = m.get("competition", {}).get("code", "")
                    # Only keep leagues we want (22 leagues)
                    if comp not in LEAGUES:
                        continue
                    out.append(_format_match(m, comp))
                if out:
                    return out
    except Exception:
        pass

    # Fallback - one by one if single call fails
    all_fixtures = []
    for code in LEAGUES.keys():
        res = await _fetch_league(code, date_from, date_to)
        all_fixtures.extend(res)
        await asyncio.sleep(0.3)
    return all_fixtures if all_fixtures else None

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
                teams.append({"id": str(t["id"]), "name": t["name"], "short_name": t.get("shortName", t["name"][:3].upper()), "crest": t.get("crest", ""), "venue": t.get("venue", "")})
            return teams
    except Exception:
        return None

async def get_team_recent_goals_real(team_id: str):
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
