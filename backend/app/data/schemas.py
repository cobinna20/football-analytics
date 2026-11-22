# Shapes of our data
# This tells the brain what a Team looks like, what a Match looks like

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Team(BaseModel):
    id: str
    name: str
    short_name: str
    crest: Optional[str] = None
    league: str = "PL"
    country: str = "England"

class Fixture(BaseModel):
    id: str
    competition: str = "PL"
    matchday: int = 1
    home_team: Team
    away_team: Team
    kickoff: datetime
    status: str = "SCHEDULED"
    venue: Optional[str] = None

class MatchHistoryEntry(BaseModel):
    opponent: str
    venue: str = "home"
    date: str
    npxg_for: float
    npxg_against: float
    goals_for: int
    goals_against: int
    minutes_leading_by_2plus: int = 0
    red_card: bool = False

class TeamStats(BaseModel):
    team_id: str
    team_name: str
    matches_played: int
    npxg: float
    npxga: float
    psxg: float
    psxg_against: float
    ppda: float
    field_tilt: float
    set_piece_xg: float
    set_piece_xga: float
    defensive_compactness: float
    last_matches: List[MatchHistoryEntry] = []

class Odds(BaseModel):
    fixture_id: str
    bookmaker: str
    home: float
    draw: float
    away: float
    over_25: float
    under_25: float
    btts_yes: float
    btts_no: float
    updated_at: datetime
