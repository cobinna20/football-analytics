import httpx
from typing import List, Optional
from ..schemas import Team, Fixture, TeamStats, Odds
from .base import BaseAdapter

BASE_URL = "https://v3.football.api-sports.io"
LEAGUE_MAP = {"PL": 39}

class ApiFootballAdapter(BaseAdapter):
    name = "api-football"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BASE_URL}{path}",
                headers={"x-apisports-key": self.api_key},
                params=params,
            )
            r.raise_for_status()
            return r.json()

    async def get_teams(self, competition: str = "PL") -> List[Team]:
        league = LEAGUE_MAP.get(competition, 39)
        data = await self._get("/teams", {"league": league, "season": 2025})
        out: List[Team] = []
        for item in data.get("response", []):
            t = item["team"]
            out.append(Team(
                id=str(t["id"]),
                name=t["name"],
                short_name=t.get("code") or t["name"][:3].upper(),
                crest=t.get("logo"),
                league=competition,
                country=t.get("country", "England"),
            ))
        return out

    async def get_fixtures(self, competition: str = "PL") -> List[Fixture]:
        league = LEAGUE_MAP.get(competition, 39)
        data = await self._get("/fixtures", {"league": league, "season": 2025, "next": 10})
        out: List[Fixture] = []
        for item in data.get("response", []):
            fx = item["fixture"]
            teams = item["teams"]
            out.append(Fixture(
                id=str(fx["id"]),
                competition=competition,
                matchday=1,
                home_team=Team(id=str(teams["home"]["id"]), name=teams["home"]["name"], short_name=teams["home"]["name"][:3].upper(), crest=teams["home"].get("logo"), league=competition),
                away_team=Team(id=str(teams["away"]["id"]), name=teams["away"]["name"], short_name=teams["away"]["name"][:3].upper(), crest=teams["away"].get("logo"), league=competition),
                kickoff=fx["date"],
                status=fx["status"].get("short", "SCHEDULED"),
                venue=fx.get("venue", {}).get("name"),
            ))
        return out
