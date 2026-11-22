from typing import List, Optional
from ..config import settings
from .cache import DiskCache
from .schemas import Team, Fixture, TeamStats, Odds
from .adapters.fallback import FallbackAdapter
from .adapters.football_data_org import FootballDataOrgAdapter
from .adapters.api_football import ApiFootballAdapter
from .adapters.odds_api import OddsApiAdapter

class DataService:
    def __init__(self):
        self.cache = DiskCache(settings.cache_dir, settings.cache_ttl_seconds)
        self.live_adapters = [
            FootballDataOrgAdapter(settings.football_data_api_key),
            ApiFootballAdapter(settings.api_football_key),
        ]
        self.odds_adapter = OddsApiAdapter(settings.odds_api_key)
        self.fallback = FallbackAdapter()

    async def get_teams(self, competition: str = "PL") -> List[Team]:
        key = f"teams:{competition}"
        cached = self.cache.get(key)
        if cached:
            return [Team(**t) for t in cached]
        for adapter in self.live_adapters:
            if not adapter.is_configured:
                continue
            try:
                teams = await adapter.get_teams(competition)
                if teams:
                    self.cache.set(key, [t.model_dump(mode="json") for t in teams])
                    return teams
            except Exception as e:
                print(f"[DataService] {adapter.name} teams failed: {e}")
        teams = await self.fallback.get_teams(competition)
        self.cache.set(key, [t.model_dump(mode="json") for t in teams], ttl=300)
        return teams

    async def get_fixtures(self, competition: str = "PL") -> List[Fixture]:
        key = f"fixtures:{competition}"
        cached = self.cache.get(key)
        if cached:
            return [Fixture(**f) for f in cached]
        for adapter in self.live_adapters:
            if not adapter.is_configured:
                continue
            try:
                fixtures = await adapter.get_fixtures(competition)
                if fixtures:
                    self.cache.set(key, [f.model_dump(mode="json") for f in fixtures])
                    return fixtures
            except Exception as e:
                print(f"[DataService] {adapter.name} fixtures failed: {e}")
        fixtures = await self.fallback.get_fixtures(competition)
        self.cache.set(key, [f.model_dump(mode="json") for f in fixtures], ttl=300)
        return fixtures

    async def get_team_stats(self, team_id: str, competition: str = "PL") -> Optional[TeamStats]:
        key = f"stats:{competition}:{team_id}"
        cached = self.cache.get(key)
        if cached:
            return TeamStats(**cached)
        stats = await self.fallback.get_team_stats(team_id, competition)
        if stats:
            self.cache.set(key, stats.model_dump(mode="json"), ttl=1800)
        return stats

    async def get_odds(self, fixture_id: str) -> Optional[Odds]:
        key = f"odds:{fixture_id}"
        cached = self.cache.get(key)
        if cached:
            return Odds(**cached)
        if self.odds_adapter.is_configured:
            try:
                odds = await self.odds_adapter.get_odds(fixture_id)
                if odds:
                    self.cache.set(key, odds.model_dump(mode="json"), ttl=600)
                    return odds
            except Exception as e:
                print(f"[DataService] odds failed: {e}")
        odds = await self.fallback.get_odds(fixture_id)
        if odds:
            self.cache.set(key, odds.model_dump(mode="json"), ttl=300)
        return odds

data_service = DataService()
