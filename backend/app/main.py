from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .data.service import data_service
from .prediction.engine import predict
from .prediction.calibration import devig_1x2, model_edge

app = FastAPI(title="Football Analytics API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    fx = next((f for f in fixtures if str(f.get("id")) == str(fixture_id)), None)
    if not fx:
        raise HTTPException(status_code=404, detail="Fixture not found")
    # fx is a dict, handle both dict and object
    if isinstance(fx, dict):
        home_id = str(fx["home_team"]["id"])
        away_id = str(fx["away_team"]["id"])
        home_name = fx["home_team"]["name"]
        away_name = fx["away_team"]["name"]
    else:
        home_id = str(fx.home_team.id)
        away_id = str(fx.away_team.id)
        home_name = fx.home_team.name
        away_name = fx.away_team.name
    home_stats = await data_service.get_team_stats(home_id, "PL")
    away_stats = await data_service.get_team_stats(away_id, "PL")
    context = {"home_rest_days": home_rest_days, "away_rest_days": away_rest_days, "home_missing_key": home_missing_key, "away_missing_key": away_missing_key, "h2h_weight": 0.0}
    result = predict(fixture_id, home_name, away_name, home_stats, away_stats, context)
    try:
        odds = await data_service.get_odds(fixture_id)
        if odds:
            # odds is a dict {"home": 2.0, "draw": 3.2, "away": 3.5}
            if isinstance(odds, dict):
                o_home = odds.get("home", 2.0)
                o_draw = odds.get("draw", 3.2)
                o_away = odds.get("away", 3.5)
            else:
                o_home = odds.home
                o_draw = odds.draw
                o_away = odds.away
            m_home, m_draw, m_away = devig_1x2(o_home, o_draw, o_away)
            result.model_edge_home = model_edge(result.home_win, m_home)
            result.model_edge_draw = model_edge(result.draw, m_draw)
            result.model_edge_away = model_edge(result.away_win, m_away)
    except Exception:
        pass
    return result
