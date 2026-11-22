# Service: REAL first, FALLBACK only if API fails
import json
from pathlib import Path
from .adapters.football_data import get_teams_real, get_fixtures_real, get_team_recent_goals_real, LEAGUES
from .adapters.odds_api import get_odds_real

BASE = Path(__file__).parent.parent.parent / "data" / "fallback"

def _load(name: str):
    p = BASE / name
    if not p.exists():
        return []
    return json.loads(p.read_text())

def _default_stats(team_id: str):
    return {
        "team_id": str(team_id), "team_name": f"Team {team_id}",
        "npxg": 1.40, "npxga": 1.40, "ppda": 11.50, "field_tilt": 50.0,
        "set_piece_xg": 0.35, "set_piece_xga": 0.35, "defensive_compactness": 68.0, "source": "default",
        "last_matches": [{"npxg_for": 1.40, "npxg_against": 1.40, "minutes_leading_by_2plus": 0, "red_card": False} for _ in range(5)],
    }

class DataService:
    async def get_teams(self, competition: str = "PL"):
        real = await get_teams_real()
        if real:
            return real
        return _load("teams.json")

    async def get_fixtures(self, competition: str = "ALL", date_from: str | None = None, date_to: str | None = None):
        real = await get_fixtures_real(competition, date_from, date_to)
        if real:
            return real
        # Fallback - filter by date if given
        all_f = _load("fixtures.json")
        if date_from and date_to:
            all_f = [f for f in all_f if date_from <= f.get("date", "")[:10] <= date_to]
        if competition and competition != "ALL":
            all_f = [f for f in all_f if f.get("competition") == competition or f.get("league_code") == competition]
        return all_f

    async def get_team_stats(self, team_id: str, competition: str = "PL"):
        matches = await get_team_recent_goals_real(team_id)
        if matches:
            goals_for, goals_against = [], []
            for m in matches:
                is_home = str(m["homeTeam"]["id"]) == str(team_id)
                hg = m["score"]["fullTime"]["home"] or 0
                ag = m["score"]["fullTime"]["away"] or 0
                if is_home:
                    goals_for.append(hg); goals_against.append(ag)
                else:
                    goals_for.append(ag); goals_against.append(hg)
            if goals_for:
                avg_for = sum(goals_for) / len(goals_for)
                avg_against = sum(goals_against) / len(goals_against)
                return {
                    "team_id": str(team_id),
                    "team_name": matches[0]["homeTeam"]["name"] if str(matches[0]["homeTeam"]["id"]) == str(team_id) else matches[0]["awayTeam"]["name"],
                    "npxg": round(avg_for * 0.95, 2), "npxga": round(avg_against * 0.95, 2),
                    "ppda": 11.5, "field_tilt": 52.0,
                    "set_piece_xg": round(avg_for * 0.25, 2), "set_piece_xga": round(avg_against * 0.25, 2),
                    "defensive_compactness": 68.0, "source": "real",
                    "last_matches": [{"npxg_for": round(g * 0.95, 2), "npxg_against": round(ga * 0.95, 2), "minutes_leading_by_2plus": 0, "red_card": False} for g, ga in zip(goals_for, goals_against)],
                }
        stats = _load("team_stats.json")
        for s in stats:
            if str(s.get("team_id")) == str(team_id):
                s["source"] = "fallback"
                return s
        return _default_stats(team_id)

    async def get_odds(self, fixture_id: str):
        fixtures = await self.get_fixtures("ALL")
        fx = next((f for f in fixtures if str(f["id"]) == str(fixture_id)), None)
        if fx:
            real_odds = await get_odds_real(fx["home_team"]["name"], fx["away_team"]["name"])
            if real_odds:
                return real_odds
        odds_list = _load("odds.json")
        for o in odds_list:
            if str(o.get("fixture_id")) == str(fixture_id):
                o["source"] = "fallback"
                return o
        return {"home": 2.0, "draw": 3.2, "away": 3.5, "source": "fallback"}

data_service = DataService()
