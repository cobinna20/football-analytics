# REAL DATA: Football-Data.org - 22 leagues, per-league (PROVEN method)
# FIX: Reverted from /matches single-call (free plan only returns Brazil)
# Back to /competitions/{code}/matches which worked for 8 leagues
# + Cache so 22 leagues = 22 requests once, then 0 requests for 5 min
import os
import asyncio
import httpx
from datetime import date, timedelta, datetime

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

# Simple cache - 5 min
_CACHE = {"data": None, "time": None, "range": ""}

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
    # Retry once if 429 (rate limit)
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{BASE}/competitions/{code}/matches", params={"dateFrom": date_from, "dateTo": date_to}, headers=HEADERS)
                if r.status_code == 429:
                    await asyncio.sleep(6)
                    continue
                if r.status_code != 200:
                    return []
                data = r.json()
                out = []
                for m in data.get("matches", []):
                    out.append(_format_match(m, code))
                return out
        except Exception:
            return []
    return []

async def get_fixtures_real(competition: str = "ALL", date_from: str | None = None, date_to: str | None = None):
    if not KEY:
        return None
    if not date_from or not date_to:
        date_from, date_to = default_range()
    if competition and competition != "ALL":
        res = await _fetch_league(competition, date_from, date_to)
        return res if res else None

    # ALL - check cache first (same 14-day range, <5 min old = return cache)
    global _CACHE
    cache_key = f"{date_from}_{date_to}"
    now = datetime.now()
    if _CACHE["data"] is not None and _CACHE["range"] == cache_key and _CACHE["time"] is not None:
        if (now - _CACHE["time"]).total_seconds() < 300:
            return _CACHE["data"]

    # Fetch one by one, small delay to stay under 10 req/min
    all_fixtures = []
    for code in LEAGUES.keys():
        res = await _fetch_league(code, date_from, date_to)
        all_fixtures.extend(res)
        await asyncio.sleep(0.6)

    # Save to cache
    if all_fixtures:
        _CACHE = {"data": all_fixtures, "time": now, "range": cache_key}
        return all_fixtures
    return None

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

# --- PHASE 8B: AUTO REST - Real rest days from last match ---
async def get_team_last_match_date(team_id: str):
    if not KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{BASE}/teams/{team_id}/matches?status=FINISHED&limit=1", headers=HEADERS)
            if r.status_code != 200:
                return None
            matches = r.json().get("matches", [])
            if not matches:
                return None
            return matches[0].get("utcDate", None)
    except Exception:
        return None

async def get_rest_days(team_id: str, fixture_date_str: str):
    try:
        last = await get_team_last_match_date(team_id)
        if not last:
            return 7
        last_date = datetime.fromisoformat(last.replace("Z", "+00:00")).date()
        if "T" in fixture_date_str:
            fix_date = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00")).date()
        else:
            fix_date = date.fromisoformat(fixture_date_str)
        diff = (fix_date - last_date).days
        if diff < 1:
            return 1
        if diff > 10:
            return 10
        return diff
    except Exception:
        return 7
