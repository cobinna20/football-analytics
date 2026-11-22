from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .data.service import data_service

app = FastAPI(title="Football Analytics API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "football-analytics"}

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
