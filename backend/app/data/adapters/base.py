# Base = template for all connectors
# Every connector must have the same shape

from abc import ABC
from typing import List, Optional
from ..schemas import Team, Fixture, TeamStats, Odds

class BaseAdapter(ABC):
    name: str = "base"

    @property
    def is_configured(self) -> bool:
        return False

    async def get_teams(self, competition: str = "PL") -> List[Team]:
        return []

    async def get_fixtures(self, competition: str = "PL") -> List[Fixture]:
        return []

    async def get_team_stats(self, team_id: str, competition: str = "PL") -> Optional[TeamStats]:
        return None

    async def get_odds(self, fixture_id: str) -> Optional[Odds]:
        return None
