from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .data.service import data_service
from .prediction.engine import predict
from .prediction.calibration import devig_1x2, model_edge

app = FastAPI(title="Football Analytics API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "football-analytics", "version": "0.2.0"}

@app.get("/api/teams")
async def list_teams(competition: str = "PL"):
    return await data_service.get_teams(competition)

@app.get("/api/fixtures")
async def list_fixtures(competition: str = "PL"):
    return await data_service.get_fixtures(competition)

@app.get("/api/teams/{team_id}/stats")
async def team_stats(team_id: str, competition: str = "PL"):
    stats = await data_service.get_team_stats(team_id, competition)
    if not stats:
        raise HTTPException(status_code=404, detail="Team stats not found")
    return stats

@app.get("/api/fixtures/{fixture_id}/odds")
async def fixture_odds(fixture_id: str):
    odds = await data_service.get_odds(fixture_id)
    if not odds:
        raise HTTPException(status_code=404, detail="Odds not found")
    return odds

@app.get("/api/fixtures/{fixture_id}/predict")
async def predict_fixture(fixture_id: str, home_rest_days: int = 7, away_rest_days: int = 7, home_missing_key: int = 0, away_missing_key: int = 0):
    fixtures = await data_service.get_fixtures("PL")
    fx = next((f for f in fixtures if f.id == fixture_id), None)
    if not fx:
        raise HTTPException(status_code=404, detail="Fixture not found")
    home_stats = await data_service.get_team_stats(fx.home_team.id, "PL")
    away_stats = await data_service.get_team_stats(fx.away_team.id, "PL")
    if not home_stats or not away_stats:
        raise HTTPException(status_code=404, detail="Stats not found")
    context = {"home_rest_days": home_rest_days, "away_rest_days": away_rest_days, "home_missing_key": home_missing_key, "away_missing_key": away_missing_key, "h2h_weight": 0.0}
    result = predict(fixture_id, fx.home_team.name, fx.away_team.name, home_stats, away_stats, context)
    odds = await data_service.get_odds(fixture_id)
    if odds:
        m_home, m_draw, m_away = devig_1x2(odds.home, odds.draw, odds.away)
        result.model_edge_home = model_edge(result.home_win, m_home)
        result.model_edge_draw = model_edge(result.draw, m_draw)
        result.model_edge_away = model_edge(result.away_win, m_away)
    return result
