from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta
from .data.service import data_service
from .prediction.engine import predict
from .prediction.calibration import devig_1x2

app = FastAPI(title="Football Analytics API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "football-analytics"}

@app.get("/api/leagues")
async def list_leagues():
    # FIX: Load ALL 25 leagues from service.py, not just 8 from football_data
    # service.py already merges: 8 from Football-Data + 17 from API-Football = 25
    from .data.service import LEAGUES as ALL_LEAGUES
    # Deduplicate by name - keep first code for each league name
    seen = {}
    for code, name in ALL_LEAGUES.items():
        if name not in seen:
            seen[name] = code
    return [{"code": code, "name": name} for name, code in seen.items()]

@app.get("/api/teams")
async def list_teams(competition: str = "PL"):
    return await data_service.get_teams(competition)

@app.get("/api/fixtures")
async def list_fixtures(competition: str = "ALL", date_from: str | None = None, date_to: str | None = None):
    # Default: 1 week ago to 1 week ahead
    if not date_from or not date_to:
        today = date.today()
        date_from = (today - timedelta(days=7)).isoformat()
        date_to = (today + timedelta(days=7)).isoformat()
    return await data_service.get_fixtures(competition, date_from, date_to)

@app.get("/api/teams/{team_id}/stats")
async def team_stats(team_id: str, competition: str = "PL"):
    stats = await data_service.get_team_stats(team_id, competition)
    if not stats:
        raise HTTPException(status_code=404, detail="Team not found")
    return stats

@app.get("/api/fixtures/{fixture_id}/odds")
async def fixture_odds(fixture_id: str):
    odds = await data_service.get_odds(fixture_id)
    if not odds:
        raise HTTPException(status_code=404, detail="Odds not found")
    return odds

@app.get("/api/fixtures/{fixture_id}/predict")
async def predict_fixture(
    fixture_id: str,
    home_rest_days: int = 3,
    away_rest_days: int = 3,
    home_missing: int = 0,
    away_missing: int = 0,
):
    fixtures = await data_service.get_fixtures("ALL")
    fx = next((f for f in fixtures if str(f.get("id")) == str(fixture_id)), None)
    if not fx:
        raise HTTPException(status_code=404, detail="Fixture not found")
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
    home_stats = await data_service.get_team_stats(home_id)
    away_stats = await data_service.get_team_stats(away_id)
    context = {
        "home_rest_days": home_rest_days,
        "away_rest_days": away_rest_days,
        "home_missing": home_missing,
        "away_missing": away_missing,
    }
    result = predict(fixture_id, home_name, away_name, home_stats, away_stats, context)
    try:
        odds = await data_service.get_odds(fixture_id)
        if odds:
            if isinstance(odds, dict):
                o_home = odds.get("home", 2.0)
                o_draw = odds.get("draw", 3.2)
                o_away = odds.get("away", 3.5)
            else:
                o_home = odds.home
                o_draw = odds.draw
                o_away = odds.away
            m_home, m_draw, m_away = devig_1x2(o_home, o_draw, o_away)
            result.model_edge_home = m_home
            result.model_edge_draw = m_draw
            result.model_edge_away = m_away
    except Exception:
        pass
    return result
