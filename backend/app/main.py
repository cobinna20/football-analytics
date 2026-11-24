import os, time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_DATA_KEY}

# MAXIMUM FREE - 12 leagues only. Do not add a 13th.
LEAGUES = [
  {"code": "PL", "name": "【entity-Premier League¦canonical_name=Premier League】"},
  {"code": "ELC", "name": "Championship"},
  {"code": "PD", "name": "【entity-La Liga¦canonical_name=La Liga】"},
  {"code": "SA", "name": "Serie A"},
  {"code": "BL1", "name": "Bundesliga"},
  {"code": "FL1", "name": "Ligue 1"},
  {"code": "DED", "name": "Eredivisie"},
  {"code": "PPL", "name": "Primeira Liga"},
  {"code": "BSA", "name": "Brasileirao"},
  {"code": "CL", "name": "【entity-Champions League¦canonical_name=Champions League】"},
  {"code": "EC", "name": "European Championship"},
  {"code": "WC", "name": "World Cup"},
]

CACHE = {}
def cache_get(key, ttl):
    if key in CACHE:
        t, v = CACHE[key]
        if time.time() - t < ttl:
            return v
    return None
def cache_set(key, val):
    CACHE[key] = (time.time(), val)

def fd_get_debug(path, params=None):
    try:
        r = requests.get(BASE + path, headers=HEADERS, params=params, timeout=12)
        try:
            data = r.json()
        except:
            data = {}
        return r.status_code, data
    except Exception as e:
        return 0, {"error": str(e)}

def map_match(m):
    home = m.get("homeTeam", {})
    away = m.get("awayTeam", {})
    comp = m.get("competition", {})
    score = m.get("score", {}).get("fullTime", {})
    return {
        "id": str(m.get("id")),
        "date": m.get("utcDate", ""),
        "status": m.get("status", ""),
        "home_score": score.get("home"),
        "away_score": score.get("away"),
        "league_code": comp.get("code", ""),
        "competition": comp.get("code", ""),
        "league_name": comp.get("name", ""),
        "home_team": {"id": home.get("id"), "name": home.get("name", ""), "short_name": home.get("shortName") or home.get("tla") or home.get("name", "")},
        "away_team": {"id": away.get("id"), "name": away.get("name", ""), "short_name": away.get("shortName") or away.get("tla") or away.get("name", "")},
    }

def fetch_one_league(args):
    code, date_str = args
    time.sleep(0.3)
    status, data = fd_get_debug(f"/competitions/{code}/matches", {"dateFrom": date_str, "dateTo": date_str})
    if status != 200 or not data or "matches" not in data:
        return []
    return [map_match(m) for m in data["matches"]]

def get_fixtures_for_date(date_str):
    key = f"fixtures:{date_str}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    # Maximum safe: 4 at a time, so 12 leagues = 3 batches, stays under 10 calls per minute
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(fetch_one_league, [(l["code"], date_str) for l in LEAGUES]))
    all_f = []
    for lst in results:
        all_f.extend(lst)
    all_f.sort(key=lambda x: x["date"])
    if all_f:
        cache_set(key, all_f)
    return all_f

def get_team_info(team_id, fixture_date):
    key = f"team:{team_id}:{fixture_date}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    rest = 7
    goals_for_avg = 1.4
    goals_against_avg = 1.2
    form = []
    last_date = None
    status, data = fd_get_debug(f"/teams/{team_id}/matches", {"dateTo": fixture_date, "limit": 6, "status": "FINISHED"})
    if status == 200 and data and "matches" in data and data["matches"]:
        matches = data["matches"]
        last = matches[-1]
        last_date = last.get("utcDate", "")[:10]
        try:
            from datetime import datetime
            d1 = datetime.strptime(fixture_date, "%Y-%m-%d")
            d2 = datetime.strptime(last_date, "%Y-%m-%d")
            rest = max(1, (d1 - d2).days)
        except:
            rest = 7
        gf, ga = [], []
        for m in matches[-5:]:
            home = m["homeTeam"]["id"] == team_id
            hs = m["score"]["fullTime"]["home"]
            aws = m["score"]["fullTime"]["away"]
            if hs is None or aws is None:
                continue
            if home:
                gf.append(hs); ga.append(aws)
                form.append("W" if hs > aws else "D" if hs == aws else "L")
            else:
                gf.append(aws); ga.append(hs)
                form.append("W" if aws > hs else "D" if aws == hs else "L")
        if gf:
            goals_for_avg = sum(gf) / len(gf)
            goals_against_avg = sum(ga) / len(ga)
    info = {"team_id": team_id, "rest": rest, "last_match_date": last_date, "goals_for_avg": round(goals_for_avg, 2), "goals_against_avg": round(goals_against_avg, 2), "form": form}
    cache_set(key, info)
    return info

def compute_prediction(fixture, home_rest, away_rest, home_missing, away_missing, home_info, away_info):
    hg = 1.45 + (home_info["goals_for_avg"] - 1.4) * 0.35 - (home_info["goals_against_avg"] - 1.2) * 0.15
    ag = 1.15 + (away_info["goals_for_avg"] - 1.4) * 0.35 - (away_info["goals_against_avg"] - 1.2) * 0.15
    if home_rest < 3: hg -= 0.25
    elif home_rest >= 7: hg += 0.08
    if away_rest < 3: ag -= 0.25
    elif away_rest >= 7: ag += 0.08
    hg -= home_missing * 0.18
    ag -= away_missing * 0.18
    hg = max(0.2, min(4.0, hg))
    ag = max(0.2, min(4.0, ag))
    diff = hg - ag
    home_win = 0.38 + diff * 0.18
    draw = 0.25 - abs(diff) * 0.04
    away_win = 1 - home_win - draw
    home_win = max(0.05, min(0.85, home_win))
    draw = max(0.08, min(0.4, draw))
    away_win = max(0.05, min(0.85, away_win))
    total = home_win + draw + away_win
    home_win /= total; draw /= total; away_win /= total
    return {
        "fixture_id": fixture["id"],
        "home_team": fixture["home_team"],
        "away_team": fixture["away_team"],
        "home_win_prob": round(home_win, 3), "draw_prob": round(draw, 3), "away_win_prob": round(away_win, 3),
        "home_win": round(home_win, 3), "draw": round(draw, 3), "away_win": round(away_win, 3),
        "predicted_home_goals": round(hg, 2), "predicted_away_goals": round(ag, 2),
        "home_goals": round(hg, 2), "away_goals": round(ag, 2),
        "predicted_score": f"{round(hg)}-{round(ag)}",
        "confidence": round(max(home_win, draw, away_win), 3),
        "explanation": f"Home {home_info['goals_for_avg']} goals avg, Away {away_info['goals_for_avg']} goals avg. Rest {home_rest} vs {away_rest} days. Missing {home_missing} vs {away_missing}.",
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/api/leagues")
def leagues():
    return LEAGUES

@app.get("/api/debug")
def debug(date: Optional[str] = "2026-11-25"):
    status, data = fd_get_debug("/competitions/PL/matches", {"dateFrom": date, "dateTo": date})
    matches_count = 0
    sample = ""
    if status == 200 and data and "matches" in data:
        matches_count = len(data["matches"])
        if matches_count > 0:
            first = data["matches"][0]
            sample = f"{first.get('homeTeam', {}).get('name')} vs {first.get('awayTeam', {}).get('name')}"
    return {
        "date_tested": date,
        "key_present": len(FOOTBALL_DATA_KEY) > 0,
        "key_length": len(FOOTBALL_DATA_KEY),
        "football_data_status": status,
        "matches_count_PL_only": matches_count,
        "sample_match": sample,
        "football_data_error": data.get("message", "") if isinstance(data, dict) else "",
    }

@app.get("/api/fixtures")
def fixtures(date: Optional[str] = None, league: Optional[str] = None):
    if date is None or date == "" or date == "ALL":
        from datetime import datetime
        date = datetime.utcnow().date().isoformat()
    all_f = get_fixtures_for_date(date)
    if league and league != "ALL":
        all_f = [f for f in all_f if f["league_code"] == league]
    return all_f

@app.get("/api/rest")
def rest(team_id: int, fixture_date: Optional[str] = None, date: Optional[str] = None):
    fd = fixture_date or date or ""
    info = get_team_info(team_id, fd)
    return {"rest": info["rest"], "team_id": team_id, "last_match_date": info["last_match_date"]}

@app.get("/api/rest-both")
def rest_both(home_team_id: int, away_team_id: int, fixture_date: Optional[str] = None, date: Optional[str] = None):
    fd = fixture_date or date or ""
    with ThreadPoolExecutor(max_workers=2) as ex:
        h, a = list(ex.map(lambda tid: get_team_info(tid, fd), [home_team_id, away_team_id]))
    return {"home_rest": h["rest"], "away_rest": a["rest"], "home_last_match_date": h["last_match_date"], "away_last_match_date": a["last_match_date"]}

@app.get("/api/fixtures/{fixture_id}/predict")
def predict(fixture_id: str, home_rest_days: int = 7, away_rest_days: int = 7, home_missing_key: int = 0, away_missing_key: int = 0):
    key = f"pred:{fixture_id}:{home_rest_days}:{away_rest_days}:{home_missing_key}:{away_missing_key}"
    c = cache_get(key, 600)
    if c is not None:
        return c
    status, data = fd_get_debug(f"/matches/{fixture_id}")
    if status != 200 or not data:
        return {"error": "fixture not found"}
    fx = map_match(data)
    fdate = fx["date"][:10]
    with ThreadPoolExecutor(max_workers=2) as ex:
        h, a = list(ex.map(lambda tid: get_team_info(tid, fdate), [fx["home_team"]["id"], fx["away_team"]["id"]]))
    pred = compute_prediction(fx, home_rest_days, away_rest_days, home_missing_key, away_missing_key, h, a)
    cache_set(key, pred)
    return pred

@app.get("/api/match-bundle")
def bundle(fixture_id: str):
    key = f"bundle:{fixture_id}"
    c = cache_get(key, 600)
    if c is not None:
        return c
    status, data = fd_get_debug(f"/matches/{fixture_id}")
    if status != 200 or not data:
        return {"error": "fixture not found"}
    fx = map_match(data)
    fdate = fx["date"][:10]
    with ThreadPoolExecutor(max_workers=2) as ex:
        h, a = list(ex.map(lambda tid: get_team_info(tid, fdate), [fx["home_team"]["id"], fx["away_team"]["id"]]))
    pred = compute_prediction(fx, h["rest"], a["rest"], 0, 0, h, a)
    out = {"fixture": fx, "rest": {"home_rest": h["rest"], "away_rest": a["rest"]}, "home_rest": h["rest"], "away_rest": a["rest"], "prediction": pred, "homeStats": h, "awayStats": a, "home_stats": h, "away_stats": a}
    cache_set(key, out)
    return out

@app.get("/api/teams/{team_id}/stats")
def team_stats(team_id: int, fixture_date: Optional[str] = None, date: Optional[str] = None):
    fd = fixture_date or date or "2026-11-25"
    return get_team_info(team_id, fd)
