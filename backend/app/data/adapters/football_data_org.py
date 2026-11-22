import httpx
from datetime import datetime
from typing import List, Optional
from ..schemas import Team, Fixture, TeamStats, Odds
from .base import BaseAdapter

BASE_URL = "https://api.football-data.org/v4"
COMPETITION_MAP = {"PL": 2021}

class FootballDataOrgAdapter(BaseAdapter):
    name = "football-data.org"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BASE_URL}{path}",
                headers={"X-Auth-Token": self.api_key},
                params=params or {},
            )
            r.raise_for_status()
            return r.json()

    async def get_teams(self, competition: str = "PL") -> List[Team]:
        comp_id = COMPETITION_MAP.get(competition, 2021)
        data = await self._get(f"/competitions/{comp_id}/teams")
        out: List[Team] = []
        for t in data.get("teams", []):
            out.append(Team(
                id=str(t["id"]),
                name=t["name"],
                short_name=t.get("shortName") or t["name"][:3].upper(),
                crest=t.get("crest"),
                league=competition,
                country="England",
            ))
        return out

    async def get_fixtures(self, competition: str = "PL") -> List[Fixture]:
        comp_id = COMPETITION_MAP.get(competition, 2021)
        data = await self._get(f"/competitions/{comp_id}/matches", {"status": "SCHEDULED"})
        out: List[Fixture] = []
        for m in data.get("matches", []):
            home = m["homeTeam"]
            away = m["awayTeam"]
            out.append(Fixture(
                id=str(m["id"]),
                competition=competition,
                matchday=m.get("matchday") or 1,
                home_team=Team(id=str(home["id"]), name=home["name"], short_name=home.get("shortName") or home["name"][:3].upper(), crest=home.get("crest"), league=competition),
                away_team=Team(id=str(away["id"]), name=away["name"], short_name=away.get("shortName") or away["name"][:3].upper(), crest=away.get("crest"), league=competition),
                kickoff=datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")),
                status=m.get("status", "SCHEDULED"),
                venue=m.get("venue"),
            ))
        return out
