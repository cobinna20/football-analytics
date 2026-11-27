import os, time, threading, math
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from datetime import datetime, timedelta
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_DATA_KEY}

LEAGUES = [
  {"code": "PL", "name": "Premier League"},
  {"code": "ELC", "name": "Championship"},
  {"code": "PD", "name": "La Liga"},
  {"code": "SA", "name": "Serie A"},
  {"code": "BL1", "name": "Bundesliga"},
  {"code": "FL1", "name": "Ligue 1"},
  {"code": "DED", "name": "Eredivisie"},
  {"code": "PPL", "name": "Primeira Liga"},
  {"code": "BSA", "name": "Brasileirao"},
  {"code": "CL", "name": "Champions League"},
  {"code": "EC", "name": "European Championship"},
  {"code": "WC", "name": "World Cup"},
]

CACHE = {}
def cache_get(k, ttl):
    if k in CACHE:
        t, v = CACHE[k]
        if time.time() - t < ttl:
            return v
    return None
def cache_set(k, v):
    CACHE[k] = (time.time(), v)

RATE_LOCK = threading.Lock()
LAST_CALLS = []
def wait_for_rate_limit():
    with RATE_LOCK:
        now = time.time()
        global LAST_CALLS
        LAST_CALLS = [t for t in LAST_CALLS if now - t < 60]
        if len(LAST_CALLS) >= 8:
            sleep_time = 60 - (now - LAST_CALLS[0]) + 1
            if sleep_time > 0:
                time.sleep(sleep_time)
        LAST_CALLS.append(time.time())

def fd_get(path, params=None):
    for attempt in range(3):
        wait_for_rate_limit()
        try:
            r = requests.get(BASE + path, headers=HEADERS, params=params, timeout=15)
            try:
                data = r.json()
            except:
                data = {}
            if r.status_code == 429:
                time.sleep(7)
                continue
            return r.status_code, data
        except Exception as e:
            time.sleep(2)
            if attempt == 2:
                return 0, {"error": str(e)}
    return 0, {}

def map_match(m):
    home = m.get("homeTeam", {}); away = m.get("awayTeam", {}); comp = m.get("competition", {})
    score = m.get("score", {}).get("fullTime", {})
    return {
        "id": str(m.get("id")), "date": m.get("utcDate", ""), "status": m.get("status", ""),
        "home_score": score.get("home"), "away_score": score.get("away"),
        "league_code": comp.get("code", ""), "competition": comp.get("code", ""), "league_name": comp.get("name", ""),
        "home_team": {"id": home.get("id"), "name": home.get("name", ""), "short_name": home.get("shortName") or home.get("tla") or home.get("name", "")},
        "away_team": {"id": away.get("id"), "name": away.get("name", ""), "short_name": away.get("shortName") or away.get("tla") or away.get("name", "")},
    }

def fetch_one_league(args):
    code, date_str = args
    status, data = fd_get(f"/competitions/{code}/matches", {"dateFrom": date_str, "dateTo": date_str})
    if status != 200 or not data or "matches" not in data:
        return []
    return [map_match(m) for m in data["matches"]]

def get_fixtures_for_date(date_str):
    key = f"fixtures:{date_str}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    with ThreadPoolExecutor(max_workers=3) as ex:
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
    rest = 7; goals_for_avg = 1.4; goals_against_avg = 1.2; form = []; last_date = None; is_default = True
    try:
        d1 = datetime.strptime(fixture_date, "%Y-%m-%d")
        date_from = (d1 - timedelta(days=90)).strftime("%Y-%m-%d")
    except:
        date_from = "2026-09-01"
    status, data = fd_get(f"/teams/{team_id}/matches", {"dateFrom": date_from, "dateTo": fixture_date, "limit": 10, "status": "FINISHED"})
    if status == 200 and data and "matches" in data and data["matches"]:
        matches = data["matches"]
        last = matches[-1]
        last_date = last.get("utcDate", "")[:10]
        try:
            d1 = datetime.strptime(fixture_date, "%Y-%m-%d"); d2 = datetime.strptime(last_date, "%Y-%m-%d")
            rest = max(1, (d1 - d2).days)
        except:
            rest = 7
        gf, ga = [], []
        for m in matches[-5:]:
            home = m["homeTeam"]["id"] == team_id
            hs = m["score"]["fullTime"]["home"]; aws = m["score"]["fullTime"]["away"]
            if hs is None or aws is None:
                continue
            if home:
                gf.append(hs); ga.append(aws); form.append("W" if hs > aws else "D" if hs == aws else "L")
            else:
                gf.append(aws); ga.append(hs); form.append("W" if aws > hs else "D" if aws == hs else "L")
        if gf:
            goals_for_avg = sum(gf)/len(gf); goals_against_avg = sum(ga)/len(ga); is_default = False
    info = {"team_id": team_id, "rest": rest, "last_match_date": last_date, "goals_for_avg": round(goals_for_avg, 2), "goals_against_avg": round(goals_against_avg, 2), "form": form, "is_default": is_default, "fd_status": status}
    if not is_default:
        cache_set(key, info)
    return info

def poisson(k, lam):
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except:
        return 0

def compute_over_under(hg, ag):
    over15 = 0; over25 = 0; over35 = 0; btts = 0
    p_home_scores = 1 - poisson(0, hg)
    p_away_scores = 1 - poisson(0, ag)
    btts = p_home_scores * p_away_scores
    for i in range(0, 11):
        for j in range(0, 11):
            p = poisson(i, hg) * poisson(j, ag)
            total = i + j
            if total >= 2:
                over15 += p
            if total >= 3:
                over25 += p
            if total >= 4:
                over35 += p
    over15 = max(0, min(1, over15)); over25 = max(0, min(1, over25)); over35 = max(0, min(1, over35))
    return {
        "over_15_prob": round(over15, 3), "under_15_prob": round(1 - over15, 3),
        "over_25_prob": round(over25, 3), "under_25_prob": round(1 - over25, 3),
        "over_35_prob": round(over35, 3), "under_35_prob": round(1 - over35, 3),
        "btts_prob": round(btts, 3), "btts": round(btts, 3),
        "over_under_pick": "Over 2.5" if over25 >= 0.55 else "Under 2.5" if over25 <= 0.45 else "No strong Over/Under",
        "over_25": round(over25, 3), "under_25": round(1 - over25, 3),
    }

def pick_two_scores(home_xg, away_xg, home_win_p, draw_p, away_win_p):
    if home_win_p >= draw_p and home_win_p >= away_win_p:
        winner = "home"
    elif draw_p >= home_win_p and draw_p >= away_win_p:
        winner = "draw"
    else:
        winner = "away"
    best_main = f"{round(home_xg)}-{round(away_xg)}"
    best_main_prob = -1
    best_main_dist = 9999
    best_worst = "1-1"
    best_worst_prob = -1
    best_worst_dist = 9999
    for h in range(0, 6):
        for a in range(0, 6):
            if h > a:
                outcome = "home"
            elif h == a:
                outcome = "draw"
            else:
                outcome = "away"
            prob = poisson(h, home_xg) * poisson(a, away_xg)
            dist = abs(h - home_xg) + abs(a - away_xg)
            if outcome == winner:
                if prob > best_main_prob or (prob == best_main_prob and dist < best_main_dist):
                    best_main_prob = prob
                    best_main_dist = dist
                    best_main = f"{h}-{a}"
            if outcome != winner:
                if prob > best_worst_prob or (prob == best_worst_prob and dist < best_worst_dist):
                    best_worst_prob = prob
                    best_worst_dist = dist
                    best_worst = f"{h}-{a}"
    return best_main, best_worst

def compute_prediction(fixture, home_rest, away_rest, home_info, away_info):
    hg = 1.45 + (home_info["goals_for_avg"] - 1.4) * 0.35 - (home_info["goals_against_avg"] - 1.2) * 0.15
    ag = 1.15 + (away_info["goals_for_avg"] - 1.4) * 0.35 - (away_info["goals_against_avg"] - 1.2) * 0.15
    if home_rest < 3: hg -= 0.25
    elif home_rest >= 7: hg += 0.08
    if away_rest < 3: ag -= 0.25
    elif away_rest >= 7: ag += 0.08
    hg = max(0.2, min(4.0, hg)); ag = max(0.2, min(4.0, ag))
    diff = hg - ag
    home_win = 0.38 + diff * 0.18; draw = 0.25 - abs(diff) * 0.04; away_win = 1 - home_win - draw
    home_win = max(0.05, min(0.85, home_win)); draw = max(0.08, min(0.4, draw)); away_win = max(0.05, min(0.85, away_win))
    total = home_win + draw + away_win; home_win /= total; draw /= total; away_win /= total
    ou = compute_over_under(hg, ag)
    main_score, worst_score = pick_two_scores(hg, ag, home_win, draw, away_win)
    return {
        "fixture_id": fixture["id"], "home_team": fixture["home_team"], "away_team": fixture["away_team"],
        "home_win_prob": round(home_win, 3), "draw_prob": round(draw, 3), "away_win_prob": round(away_win, 3),
        "home_win": round(home_win, 3), "draw": round(draw, 3), "away_win": round(away_win, 3),
        "predicted_home_goals": round(hg, 2), "predicted_away_goals": round(ag, 2),
        "home_goals": round(hg, 2), "away_goals": round(ag, 2),
        "predicted_score": main_score,
        "main_score": main_score,
        "most_likely_score": main_score,
        "worst_score": worst_score,
        "worst_scenario_score": worst_score,
        "cover_score": worst_score,
        "confidence": round(max(home_win, draw, away_win), 3),
        "explanation": f"Home {home_info['goals_for_avg']} goals avg, Away {away_info['goals_for_avg']} goals avg. Rest {home_rest} vs {away_rest} days. Form Home {','.join(home_info['form']) or 'N/A'} vs Away {','.join(away_info['form']) or 'N/A'}.",
        "two_score_explanation": f"Most Likely {main_score}, Worst Scenario / Cover {worst_score}.",
        **ou,
    }

@app.get("/health")
def health(): return {"status": "ok"}
@app.get("/")
def root(): return {"status": "ok"}
@app.get("/api/leagues")
def leagues(): return LEAGUES
@app.get("/api/debug")
def debug(date: Optional[str] = "2026-11-28"):
    status, data = fd_get("/competitions/PL/matches", {"dateFrom": date, "dateTo": date})
    cnt = 0; sample = ""
    if status == 200 and data and "matches" in data:
        cnt = len(data["matches"])
        if cnt > 0:
            f = data["matches"][0]; sample = f"{f.get('homeTeam', {}).get('name')} vs {f.get('awayTeam', {}).get('name')}"
    return {"date_tested": date, "key_present": len(FOOTBALL_DATA_KEY) > 0, "football_data_status": status, "matches_count_PL_only": cnt, "sample_match": sample}
@app.get("/api/debug-team")
def debug_team(team_id: int, date: Optional[str] = "2026-11-28"):
    return get_team_info(team_id, date)
@app.get("/api/fixtures")
def fixtures(date: Optional[str] = None, league: Optional[str] = None):
    if not date or date == "ALL":
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
def predict(fixture_id: str, home_rest_days: int = 7, away_rest_days: int = 7):
    key = f"pred:{fixture_id}:{home_rest_days}:{away_rest_days}"
    c = cache_get(key, 600)
    if c is not None: return c
    status, data = fd_get(f"/matches/{fixture_id}")
    if status != 200 or not data: return {"error": "fixture not found"}
    fx = map_match(data); fdate = fx["date"][:10]
    with ThreadPoolExecutor(max_workers=2) as ex:
        h, a = list(ex.map(lambda tid: get_team_info(tid, fdate), [fx["home_team"]["id"], fx["away_team"]["id"]]))
    pred = compute_prediction(fx, home_rest_days, away_rest_days, h, a)
    cache_set(key, pred); return pred
@app.get("/api/match-bundle")
def bundle(fixture_id: str):
    key = f"bundle:{fixture_id}"
    c = cache_get(key, 600)
    if c is not None: return c
    status, data = fd_get(f"/matches/{fixture_id}")
    if status != 200 or not data: return {"error": "fixture not found"}
    fx = map_match(data); fdate = fx["date"][:10]
    with ThreadPoolExecutor(max_workers=2) as ex:
        h, a = list(ex.map(lambda tid: get_team_info(tid, fdate), [fx["home_team"]["id"], fx["away_team"]["id"]]))
    pred = compute_prediction(fx, h["rest"], a["rest"], h, a)
    out = {"fixture": fx, "rest": {"home_rest": h["rest"], "away_rest": a["rest"]}, "home_rest": h["rest"], "away_rest": a["rest"], "prediction": pred, "homeStats": h, "awayStats": a, "home_stats": h, "away_stats": a, "is_default": h.get("is_default") and a.get("is_default")}
    if not out["is_default"]:
        cache_set(key, out)
    return out
@app.get("/api/teams/{team_id}/stats")
def team_stats(team_id: int, fixture_date: Optional[str] = None, date: Optional[str] = None):
    fd = fixture_date or date or "2026-11-28"
    return get_team_info(team_id, fd)
