# Prediction shapes
# What a guess looks like

from typing import List
from pydantic import BaseModel

class ScorelineProb(BaseModel):
    home_goals: int
    away_goals: int
    probability: float

class PredictionResult(BaseModel):
    fixture_id: str
    home_team: str
    away_team: str
    home_win: float
    draw: float
    away_win: float
    over_25: float
    under_25: float
    btts_yes: float
    btts_no: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str
    scorelines: List[ScorelineProb]
    model_edge_home: float = 0.0
    model_edge_draw: float = 0.0
    model_edge_away: float = 0.0
