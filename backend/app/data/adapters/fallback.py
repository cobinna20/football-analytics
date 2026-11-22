# Fallback = backup data
# If internet fails or no keys, we use local JSON files

import json
from pathlib import Path
from typing import List, Optional
from ..schemas import Team, Fixture, TeamStats, Odds
from .base import BaseAdapter

FALLBACK_DIR = Path(__file__).resolve().parent.parent / "fallback_data"

class FallbackAdapter(BaseAdapter):
    name = "fallback-json"

    @property
    def is_configured(self) -> bool:
        return True

    def _load(self, name: str):
        p = FALLBACK_DIR / name
        return json.loads(p.read_text())

    async def get_teams(self, competition: str = "PL") -> List[Team]:
        return [Team(**t) for t in self._load("teams.json")]

    async def get_fixtures(self, competition: str = "PL") -> List[Fixture]:
        return [Fixture(**f) for f in self._load("fixtures.json")]

    async def get_team_stats(self, team_id: str, competition: str = "PL") -> Optional[TeamStats]:
        data = self._load("team_stats.json")
        raw = data.get(str(team_id))
        if not raw:
            return None
        return TeamStats(**raw)

    async def get_odds(self, fixture_id: str) -> Optional[Odds]:
        data = self._load("odds.json")
        raw = data.get(str(fixture_id))
        if not raw:
            return None
        return Odds(**raw)
