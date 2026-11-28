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

# ---------- NEW ONLY - SMART CONFIDENCE HELPERS ----------
def form_points(form_list):
    try:
        pts = 0
        for f in form_list or []:
            if f == "W": pts += 3
            elif f == "D": pts += 1
        return pts
    except:
        return 0

def get_next_match(team_id, fixture_date):
    key = f"next:{team_id}:{fixture_date}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    out = {"has_next": False, "days_until": 99, "importance": 0, "importance_label": "No next match in 14 days", "opponent": "", "competition": "", "competition_code": "", "next_date": ""}
    try:
        d1 = datetime.strptime(fixture_date, "%Y-%m-%d")
        date_from = (d1 + timedelta(days=1)).strftime("%Y-%m-%d")
        date_to = (d1 + timedelta(days=14)).strftime("%Y-%m-%d")
    except:
        date_from = fixture_date; date_to = fixture_date
    status, data = fd_get(f"/teams/{team_id}/matches", {"dateFrom": date_from, "dateTo": date_to, "limit": 10})
    if status != 200 or not data or "matches" not in data or not data["matches"]:
        cache_set(key, out); return out
    try:
        matches = sorted(data["matches"], key=lambda m: m.get("utcDate", ""))
        if not matches:
            cache_set(key, out); return out
        nxt = matches[0]
        next_date = nxt.get("utcDate", "")[:10]
        try:
            d1b = datetime.strptime(fixture_date, "%Y-%m-%d"); d2b = datetime.strptime(next_date, "%Y-%m-%d")
            days_until = (d2b - d1b).days
        except:
            days_until = 99
        comp = nxt.get("competition", {}) or {}
        comp_code = comp.get("code", ""); comp_name = comp.get("name", "")
        home = nxt.get("homeTeam", {}) or {}; away = nxt.get("awayTeam", {}) or {}
        if home.get("id") == team_id:
            opp = away.get("name", "")
        else:
            opp = home.get("name", "")
        importance = 0; label = "Low"
        if days_until <= 3:
            if comp_code == "CL": importance = 10; label = "VERY HIGH - Champions League in " + str(days_until) + " days"
            elif comp_code in ["EC", "WC"]: importance = 9; label = "VERY HIGH - Tournament in " + str(days_until) + " days"
            else: importance = 7; label = "HIGH - League match in " + str(days_until) + " days"
        elif days_until <= 7:
            if comp_code == "CL": importance = 6; label = "MEDIUM-HIGH - Champions League in " + str(days_until) + " days"
            elif comp_code in ["EC", "WC"]: importance = 5; label = "MEDIUM - Tournament in " + str(days_until) + " days"
            else: importance = 3; label = "LOW-MEDIUM - League in " + str(days_until) + " days"
        else:
            importance = 0; label = "Low - Next in " + str(days_until) + " days"
        out = {"has_next": True, "days_until": days_until, "importance": importance, "importance_label": label, "opponent": opp, "competition": comp_name, "competition_code": comp_code, "next_date": next_date}
        cache_set(key, out); return out
    except:
        cache_set(key, out); return out

def get_standings_map(league_code):
    if not league_code: return {}
    key = f"standmap:{league_code}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    m = {}
    status, data = fd_get(f"/competitions/{league_code}/standings")
    if status == 200 and data and "standings" in data:
        for s in data.get("standings", []):
            if s.get("type") != "TOTAL": continue
            for row in s.get("table", []):
                try:
                    team = row.get("team", {}) or {}
                    tid = team.get("id")
                    if tid is None: continue
                    m[tid] = {"position": row.get("position"), "points": row.get("points"), "played": row.get("playedGames"), "won": row.get("won"), "drawn": row.get("draw"), "lost": row.get("lost"), "gf": row.get("goalsFor"), "ga": row.get("goalsAgainst"), "gd": row.get("goalDifference"), "form": row.get("form", ""), "team_name": team.get("name", "")}
                except: continue
    if m:
        cache_set(key, m)
    return m

def get_h2h_data(home_id, away_id, fixture_date, home_name="", away_name=""):
    key = f"h2hdata:{home_id}:{away_id}:{fixture_date}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    out = {"total": 0, "home_wins": 0, "draws": 0, "away_wins": 0, "home_goals": 0, "away_goals": 0, "btts": 0, "over25": 0, "meetings": []}
    try:
        d1 = datetime.strptime(fixture_date, "%Y-%m-%d")
        date_from = (d1 - timedelta(days=730)).strftime("%Y-%m-%d")
    except:
        date_from = "2024-11-28"
    s2, d2 = fd_get(f"/teams/{home_id}/matches", {"dateFrom": date_from, "dateTo": fixture_date, "limit": 50, "status": "FINISHED"})
    if s2 != 200 or not d2 or "matches" not in d2:
        cache_set(key, out); return out
    meetings = []
    for m in d2["matches"]:
        try:
            h = m.get("homeTeam", {}) or {}; a = m.get("awayTeam", {}) or {}
            h_id = h.get("id"); a_id = a.get("id")
            if not ((h_id == home_id and a_id == away_id) or (h_id == away_id and a_id == home_id)): continue
            hs = m.get("score", {}).get("fullTime", {}).get("home"); aws = m.get("score", {}).get("fullTime", {}).get("away")
            if hs is None or aws is None: continue
            meetings.append({"date": m.get("utcDate", "")[:10], "home": h.get("name", ""), "away": a.get("name", ""), "home_score": hs, "away_score": aws})
        except: continue
    meetings = sorted(meetings, key=lambda x: x.get("date", ""), reverse=True)[:10]
    hw = 0; dr = 0; aw = 0; hg = 0; ag = 0; btts = 0; o25 = 0
    for m in meetings:
        if m["home"] == home_name:
            my_hs = m["home_score"]; my_aws = m["away_score"]
        else:
            my_hs = m["away_score"]; my_aws = m["home_score"]
        hg += my_hs; ag += my_aws
        if my_hs > my_aws: hw += 1
        elif my_hs == my_aws: dr += 1
        else: aw += 1
        if my_hs > 0 and my_aws > 0: btts += 1
        if (my_hs + my_aws) >= 3: o25 += 1
    out = {"total": len(meetings), "home_wins": hw, "draws": dr, "away_wins": aw, "home_goals": hg, "away_goals": ag, "btts": btts, "over25": o25, "meetings": meetings}
    if meetings:
        cache_set(key, out)
    return out

def compute_smart_confidence(home_win, draw, away_win, home_info, away_info, h2h_data, home_standing, away_standing, home_next, away_next, home_rest, away_rest, home_name="", away_name=""):
    try:
        base_pct = round(max(home_win, draw, away_win) * 100)
        if home_win >= draw and home_win >= away_win: winner = "home"
        elif away_win >= home_win and away_win >= draw: winner = "away"
        else: winner = "draw"
        adjustments = []
        # FORM
        hf = form_points(home_info.get("form", [])); af = form_points(away_info.get("form", []))
        if winner == "home":
            diff = hf - af
            if diff >= 6: adjustments.append({"factor": "Form", "detail": f"Winner Form {hf} pts vs {af} pts - much better form", "points": 8})
            elif diff >= 3: adjustments.append({"factor": "Form", "detail": f"Winner Form {hf} pts vs {af} pts - better form", "points": 4})
            elif diff <= -6: adjustments.append({"factor": "Form", "detail": f"Winner Form {hf} pts vs {af} pts - much worse form, upset risk", "points": -8})
            elif diff <= -3: adjustments.append({"factor": "Form", "detail": f"Winner Form {hf} pts vs {af} pts - worse form", "points": -4})
            else: adjustments.append({"factor": "Form", "detail": f"Form balanced {hf} pts vs {af} pts", "points": 0})
        elif winner == "away":
            diff = af - hf
            if diff >= 6: adjustments.append({"factor": "Form", "detail": f"Winner Form {af} pts vs {hf} pts - much better form", "points": 8})
            elif diff >= 3: adjustments.append({"factor": "Form", "detail": f"Winner Form {af} pts vs {hf} pts - better form", "points": 4})
            elif diff <= -6: adjustments.append({"factor": "Form", "detail": f"Winner Form {af} pts vs {hf} pts - much worse form, upset risk", "points": -8})
            elif diff <= -3: adjustments.append({"factor": "Form", "detail": f"Winner Form {af} pts vs {hf} pts - worse form", "points": -4})
            else: adjustments.append({"factor": "Form", "detail": f"Form balanced {af} pts vs {hf} pts", "points": 0})
        else:
            if abs(hf - af) <= 2: adjustments.append({"factor": "Form", "detail": f"Form balanced {hf} pts vs {af} pts - draw plausible", "points": 4})
            elif abs(hf - af) >= 6: adjustments.append({"factor": "Form", "detail": f"Form gap big {hf} vs {af} - draw less likely", "points": -6})
            else: adjustments.append({"factor": "Form", "detail": f"Form {hf} pts vs {af} pts", "points": -2})
        # H2H
        if h2h_data and h2h_data.get("total", 0) >= 1:
            total = h2h_data.get("total", 0); hw = h2h_data.get("home_wins", 0); aw = h2h_data.get("away_wins", 0); dr = h2h_data.get("draws", 0)
            if winner == "home":
                d = hw - aw
                if d >= 2: adjustments.append({"factor": "H2H", "detail": f"H2H Home leads {hw}-{dr}-{aw} in {total} meetings", "points": 6})
                elif d == 1: adjustments.append({"factor": "H2H", "detail": f"H2H Home leads {hw}-{dr}-{aw}", "points": 3})
                elif d <= -2: adjustments.append({"factor": "H2H", "detail": f"H2H Away dominates {hw}-{dr}-{aw} - winner struggles vs this opponent", "points": -8})
                elif d == -1: adjustments.append({"factor": "H2H", "detail": f"H2H Away leads {hw}-{dr}-{aw}", "points": -4})
                else: adjustments.append({"factor": "H2H", "detail": f"H2H balanced {hw}-{dr}-{aw}", "points": 0})
            elif winner == "away":
                d = aw - hw
                if d >= 2: adjustments.append({"factor": "H2H", "detail": f"H2H Away leads {hw}-{dr}-{aw} in {total} meetings", "points": 6})
                elif d == 1: adjustments.append({"factor": "H2H", "detail": f"H2H Away leads {hw}-{dr}-{aw}", "points": 3})
                elif d <= -2: adjustments.append({"factor": "H2H", "detail": f"H2H Home dominates {hw}-{dr}-{aw} - winner struggles vs this opponent", "points": -8})
                elif d == -1: adjustments.append({"factor": "H2H", "detail": f"H2H Home leads {hw}-{dr}-{aw}", "points": -4})
                else: adjustments.append({"factor": "H2H", "detail": f"H2H balanced {hw}-{dr}-{aw}", "points": 0})
            else:
                if dr >= 2 and total >= 4: adjustments.append({"factor": "H2H", "detail": f"H2H they draw often {hw}-{dr}-{aw}", "points": 3})
                elif abs(hw - aw) >= 2: adjustments.append({"factor": "H2H", "detail": f"H2H one team dominates {hw}-{dr}-{aw} - draw less likely", "points": -5})
                else: adjustments.append({"factor": "H2H", "detail": f"H2H balanced {hw}-{dr}-{aw}", "points": 0})
        else:
            adjustments.append({"factor": "H2H", "detail": "No H2H meetings found - no adjustment", "points": 0})
        # STANDING
        if home_standing and away_standing and home_standing.get("position") and away_standing.get("position"):
            hp = home_standing.get("position"); ap = away_standing.get("position")
            if winner == "home":
                pdiff = ap - hp
                if pdiff >= 8: adjustments.append({"factor": "Table", "detail": f"Winner #{hp} is {pdiff} places above loser #{ap}", "points": 5})
                elif pdiff >= 4: adjustments.append({"factor": "Table", "detail": f"Winner #{hp} above loser #{ap}", "points": 3})
                elif pdiff <= -8: adjustments.append({"factor": "Table", "detail": f"Winner #{hp} is {abs(pdiff)} places BELOW loser #{ap} - upset risk", "points": -7})
                elif pdiff <= -4: adjustments.append({"factor": "Table", "detail": f"Winner #{hp} below loser #{ap}", "points": -4})
                else: adjustments.append({"factor": "Table", "detail": f"Table close #{hp} vs #{ap}", "points": 0})
            elif winner == "away":
                pdiff = hp - ap
                if pdiff >= 8: adjustments.append({"factor": "Table", "detail": f"Winner #{ap} is {pdiff} places above loser #{hp}", "points": 5})
                elif pdiff >= 4: adjustments.append({"factor": "Table", "detail": f"Winner #{ap} above loser #{hp}", "points": 3})
                elif pdiff <= -8: adjustments.append({"factor": "Table", "detail": f"Winner #{ap} is {abs(pdiff)} places BELOW loser #{hp} - upset risk", "points": -7})
                elif pdiff <= -4: adjustments.append({"factor": "Table", "detail": f"Winner #{ap} below loser #{hp}", "points": -4})
                else: adjustments.append({"factor": "Table", "detail": f"Table close #{hp} vs #{ap}", "points": 0})
            else:
                if abs(hp - ap) <= 3: adjustments.append({"factor": "Table", "detail": f"Table close #{hp} vs #{ap} - draw plausible", "points": 3})
                elif abs(hp - ap) >= 8: adjustments.append({"factor": "Table", "detail": f"Table gap big #{hp} vs #{ap} - draw less likely", "points": -5})
                else: adjustments.append({"factor": "Table", "detail": f"Table #{hp} vs #{ap}", "points": 0})
        else:
            adjustments.append({"factor": "Table", "detail": "Table not available for this competition - no adjustment", "points": 0})
        # GOALS
        h_gd = float(home_info.get("goals_for_avg", 1.4)) - float(home_info.get("goals_against_avg", 1.2))
        a_gd = float(away_info.get("goals_for_avg", 1.4)) - float(away_info.get("goals_against_avg", 1.2))
        if winner == "home":
            gdiff = h_gd - a_gd
            if gdiff >= 0.8: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff +{round(gdiff,2)} per game better (GF-GA)", "points": 5})
            elif gdiff >= 0.4: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff +{round(gdiff,2)} better", "points": 3})
            elif gdiff <= -0.8: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff {round(gdiff,2)} worse - scores less, concedes more", "points": -5})
            elif gdiff <= -0.4: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff {round(gdiff,2)} worse", "points": -3})
            else: adjustments.append({"factor": "Goals", "detail": f"Goals diff similar Home {round(h_gd,2)} vs Away {round(a_gd,2)}", "points": 0})
        elif winner == "away":
            gdiff = a_gd - h_gd
            if gdiff >= 0.8: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff +{round(gdiff,2)} per game better", "points": 5})
            elif gdiff >= 0.4: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff +{round(gdiff,2)} better", "points": 3})
            elif gdiff <= -0.8: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff {round(gdiff,2)} worse", "points": -5})
            elif gdiff <= -0.4: adjustments.append({"factor": "Goals", "detail": f"Winner goals diff {round(gdiff,2)} worse", "points": -3})
            else: adjustments.append({"factor": "Goals", "detail": f"Goals diff similar Away {round(a_gd,2)} vs Home {round(h_gd,2)}", "points": 0})
        else:
            if abs(h_gd - a_gd) <= 0.3: adjustments.append({"factor": "Goals", "detail": f"Goals diff similar {round(h_gd,2)} vs {round(a_gd,2)} - draw plausible", "points": 3})
            else: adjustments.append({"factor": "Goals", "detail": f"Goals diff gap {round(h_gd,2)} vs {round(a_gd,2)}", "points": -3})
        # NEXT MATCH / ROTATION - REDUCE CONFIDENCE IF PLAYERS MAY BE RESTED
        rotation_texts = []
        rotation_risk = False
        h_imp = (home_next or {}).get("importance", 0); a_imp = (away_next or {}).get("importance", 0)
        h_days = (home_next or {}).get("days_until", 99); a_days = (away_next or {}).get("days_until", 99)
        if winner == "home":
            if h_imp >= 7:
                adjustments.append({"factor": "Next Match / Resting", "detail": f"ROTATION RISK: Winner {home_name} plays {home_next.get('competition','')} vs {home_next.get('opponent','')} in {h_days} days - may rest starters", "points": -10}); rotation_texts.append(f"{home_name} may rest players for {home_next.get('competition','')} vs {home_next.get('opponent','')} in {h_days} days"); rotation_risk = True
            elif h_imp >= 4:
                adjustments.append({"factor": "Next Match / Resting", "detail": f"Winner {home_name} has next match in {h_days} days ({home_next.get('competition','')}) - slight rotation risk", "points": -5}); rotation_risk = True
            if a_imp >= 7:
                adjustments.append({"factor": "Next Match / Resting", "detail": f"Loser {away_name} may also rest for {away_next.get('competition','')} in {a_days} days - game less predictable", "points": -4}); rotation_risk = True
        elif winner == "away":
            if a_imp >= 7:
                adjustments.append({"factor": "Next Match / Resting", "detail": f"ROTATION RISK: Winner {away_name} plays {away_next.get('competition','')} vs {away_next.get('opponent','')} in {a_days} days - may rest starters", "points": -10}); rotation_texts.append(f"{away_name} may rest players for {away_next.get('competition','')} vs {away_next.get('opponent','')} in {a_days} days"); rotation_risk = True
            elif a_imp >= 4:
                adjustments.append({"factor": "Next Match / Resting", "detail": f"Winner {away_name} has next match in {a_days} days ({away_next.get('competition','')}) - slight rotation risk", "points": -5}); rotation_risk = True
            if h_imp >= 7:
                adjustments.append({"factor": "Next Match / Resting", "detail": f"Loser {home_name} may also rest for {home_next.get('competition','')} in {h_days} days", "points": -4}); rotation_risk = True
        else:
            if h_imp >= 7 or a_imp >= 7:
                adjustments.append({"factor": "Next Match / Resting", "detail": "One or both teams have big match in 2-3 days - may rest players, draw less certain", "points": -6}); rotation_risk = True
            elif h_imp >= 4 or a_imp >= 4:
                adjustments.append({"factor": "Next Match / Resting", "detail": "Next match in few days - slight rotation risk", "points": -3})
        if winner in ["home", "away"]:
            if home_rest is not None and home_rest < 3 and winner == "home":
                adjustments.append({"factor": "Rest", "detail": f"Winner rested only {home_rest} days - tired", "points": -3})
            if away_rest is not None and away_rest < 3 and winner == "away":
                adjustments.append({"factor": "Rest", "detail": f"Winner rested only {away_rest} days - tired", "points": -3})
        total_adj = sum(a["points"] for a in adjustments)
        final_pct = max(5, min(92, base_pct + total_adj))
        if final_pct >= 70: label = "SUPER LOCK"; advice = "Very safe. Strong pick."
        elif final_pct >= 60: label = "HIGH CONFIDENCE"; advice = "Good pick. Play Main, cover Worst."
        elif final_pct >= 50: label = "MEDIUM CONFIDENCE"; advice = "Play Main + cover Worst. Small stake only."
        else: label = "LOW - HIGH RISK TRAP - SKIP"; advice = "Skip this match. Too risky."
        expl_parts = []
        expl_parts.append(f"Base {base_pct}% from probability.")
        for a in adjustments:
            if a["points"] != 0:
                sign = "+" if a["points"] > 0 else ""
                expl_parts.append(f"{a['factor']} {sign}{a['points']}%: {a['detail']}.")
        expl = " ".join(expl_parts) + f" Final {final_pct}% - {label}."
        return {"base_pct": base_pct, "final_pct": final_pct, "confidence": round(final_pct/100, 3), "label": label, "advice": advice, "adjustments": adjustments, "explanation": expl, "rotation_risk": rotation_risk, "rotation_texts": rotation_texts, "winner": winner, "form_points_home": hf, "form_points_away": af}
    except Exception as e:
        base_pct = round(max(home_win, draw, away_win) * 100)
        return {"base_pct": base_pct, "final_pct": base_pct, "confidence": round(base_pct/100, 3), "label": "MEDIUM CONFIDENCE", "advice": "", "adjustments": [], "explanation": f"Base {base_pct}% - Smart breakdown not available.", "rotation_risk": False, "rotation_texts": [], "winner": "home", "form_points_home": 0, "form_points_away": 0}

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

def compute_prediction(fixture, home_rest, away_rest, home_info, away_info, h2h_data=None, home_standing=None, away_standing=None, home_next=None, away_next=None):
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
    # SMART CONFIDENCE - uses Form, H2H, Table, Goals, Next Match / Resting
    try:
        smart = compute_smart_confidence(home_win, draw, away_win, home_info, away_info, h2h_data, home_standing, away_standing, home_next, away_next, home_rest, away_rest, home_name=fixture["home_team"].get("name",""), away_name=fixture["away_team"].get("name",""))
    except:
        smart = {"final_pct": round(max(home_win, draw, away_win)*100), "confidence": round(max(home_win, draw, away_win),3), "base_pct": round(max(home_win, draw, away_win)*100), "label": "MEDIUM CONFIDENCE", "advice": "", "adjustments": [], "explanation": "", "rotation_risk": False, "rotation_texts": [], "winner": "home", "form_points_home": 0, "form_points_away": 0}
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
        "confidence": smart["confidence"],
        "confidence_pct": smart["final_pct"],
        "base_confidence": round(smart["base_pct"]/100, 3),
        "base_confidence_pct": smart["base_pct"],
        "confidence_label": smart["label"],
        "confidence_advice": smart["advice"],
        "confidence_breakdown": smart["adjustments"],
        "confidence_explanation": smart["explanation"],
        "rotation_risk": smart["rotation_risk"],
        "rotation_text": " | ".join(smart["rotation_texts"]) if smart["rotation_texts"] else "",
        "rotation_texts": smart["rotation_texts"],
        "home_next_match": home_next or {},
        "away_next_match": away_next or {},
        "home_standing": home_standing or {},
        "away_standing": away_standing or {},
        "h2h": h2h_data or {},
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
    try:
        with ThreadPoolExecutor(max_workers=3) as ex2:
            fut = {}
            fut["h2h"] = ex2.submit(get_h2h_data, fx["home_team"]["id"], fx["away_team"]["id"], fdate, fx["home_team"]["name"], fx["away_team"]["name"])
            fut["stand"] = ex2.submit(get_standings_map, fx.get("league_code",""))
            fut["next_h"] = ex2.submit(get_next_match, fx["home_team"]["id"], fdate)
            fut["next_a"] = ex2.submit(get_next_match, fx["away_team"]["id"], fdate)
            h2h_d = fut["h2h"].result(); stand_map = fut["stand"].result(); h_next = fut["next_h"].result(); a_next = fut["next_a"].result()
        h_stand = stand_map.get(fx["home_team"]["id"], {}) if stand_map else {}
        a_stand = stand_map.get(fx["away_team"]["id"], {}) if stand_map else {}
    except:
        h2h_d = None; h_stand = {}; a_stand = {}; h_next = {}; a_next = {}
    pred = compute_prediction(fx, home_rest_days, away_rest_days, h, a, h2h_data=h2h_d, home_standing=h_stand, away_standing=a_stand, home_next=h_next, away_next=a_next)
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
    try:
        with ThreadPoolExecutor(max_workers=4) as ex2:
            fut = {}
            fut["h2h"] = ex2.submit(get_h2h_data, fx["home_team"]["id"], fx["away_team"]["id"], fdate, fx["home_team"]["name"], fx["away_team"]["name"])
            fut["stand"] = ex2.submit(get_standings_map, fx.get("league_code",""))
            fut["next_h"] = ex2.submit(get_next_match, fx["home_team"]["id"], fdate)
            fut["next_a"] = ex2.submit(get_next_match, fx["away_team"]["id"], fdate)
            h2h_d = fut["h2h"].result(); stand_map = fut["stand"].result(); h_next = fut["next_h"].result(); a_next = fut["next_a"].result()
        h_stand = stand_map.get(fx["home_team"]["id"], {}) if stand_map else {}
        a_stand = stand_map.get(fx["away_team"]["id"], {}) if stand_map else {}
    except:
        h2h_d = None; h_stand = {}; a_stand = {}; h_next = {}; a_next = {}
    pred = compute_prediction(fx, h["rest"], a["rest"], h, a, h2h_data=h2h_d, home_standing=h_stand, away_standing=a_stand, home_next=h_next, away_next=a_next)
    out = {"fixture": fx, "rest": {"home_rest": h["rest"], "away_rest": a["rest"]}, "home_rest": h["rest"], "away_rest": a["rest"], "prediction": pred, "homeStats": h, "awayStats": a, "home_stats": h, "away_stats": a, "is_default": h.get("is_default") and a.get("is_default"), "h2h": h2h_d, "standings_map": stand_map if 'stand_map' in locals() else {}, "home_next_match": h_next, "away_next_match": a_next}
    if not out["is_default"]:
        cache_set(key, out)
    return out
@app.get("/api/teams/{team_id}/stats")
def team_stats(team_id: int, fixture_date: Optional[str] = None, date: Optional[str] = None):
    fd = fixture_date or date or "2026-11-28"
    return get_team_info(team_id, fd)

@app.get("/api/standings")
def standings(league_code: Optional[str] = None, league_name: Optional[str] = None):
    code = (league_code or "").upper()
    if code not in [l["code"] for l in LEAGUES]:
        if league_name:
            for l in LEAGUES:
                if l["name"].lower() in league_name.lower() or league_name.lower() in l["name"].lower():
                    code = l["code"]
                    break
    if code not in [l["code"] for l in LEAGUES]:
        return {"error": "Unknown league", "standings": [], "table": []}
    key = f"standings:{code}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    status, data = fd_get(f"/competitions/{code}/standings")
    if status != 200 or not data or "standings" not in data:
        return {"error": "Standings not available", "standings": [], "table": []}
    total = []
    for s in data.get("standings", []):
        if s.get("type") != "TOTAL":
            continue
        for row in s.get("table", []):
            try:
                team = row.get("team", {}) or {}
                tname = team.get("shortName") or team.get("tla") or team.get("name", "")
                total.append({
                    "position": row.get("position"), "pos": row.get("position"),
                    "team": tname, "team_name": team.get("name", ""), "name": team.get("name", ""),
                    "played": row.get("playedGames"), "games": row.get("playedGames"), "p": row.get("playedGames"),
                    "won": row.get("won"), "w": row.get("won"),
                    "drawn": row.get("draw"), "d": row.get("draw"),
                    "lost": row.get("lost"), "l": row.get("lost"),
                    "gf": row.get("goalsFor"), "goals_for": row.get("goalsFor"), "goalsFor": row.get("goalsFor"),
                    "ga": row.get("goalsAgainst"), "goals_against": row.get("goalsAgainst"), "goalsAgainst": row.get("goalsAgainst"),
                    "gd": row.get("goalDifference"), "goal_diff": row.get("goalDifference"),
                    "points": row.get("points"), "pts": row.get("points"),
                    "form": row.get("form", ""),
                })
            except:
                continue
    league_name_out = ""
    for l in LEAGUES:
        if l["code"] == code:
            league_name_out = l["name"]
            break
    out = {"league_code": code, "league_name": league_name_out, "standings": total, "table": total}
    if total:
        cache_set(key, out)
    return out

@app.get("/api/h2h")
def h2h(fixture_id: str):
    key = f"h2h:{fixture_id}"
    c = cache_get(key, 3600)
    if c is not None:
        return c
    status, data = fd_get(f"/matches/{fixture_id}")
    if status != 200 or not data:
        return {"error": "fixture not found", "meetings": [], "total": 0}
    fx = map_match(data)
    home_id = fx["home_team"]["id"]
    away_id = fx["away_team"]["id"]
    home_name = fx["home_team"]["name"]
    away_name = fx["away_team"]["name"]
    fdate = fx["date"][:10] if fx["date"] else "2026-11-28"
    h2h_block = data.get("head2head", {}) or {}
    total_from_block = h2h_block.get("numberOfMatches", 0)
    d = get_h2h_data(home_id, away_id, fdate, home_name, away_name)
    meetings = d.get("meetings", []); home_wins = d.get("home_wins", 0); draws = d.get("draws", 0); away_wins = d.get("away_wins", 0); home_goals = d.get("home_goals", 0); away_goals = d.get("away_goals", 0); btts = d.get("btts", 0); over25 = d.get("over25", 0)
    if len(meetings) == 0 and h2h_block:
        try:
            ht = h2h_block.get("homeTeam", {}) or {}
            at = h2h_block.get("awayTeam", {}) or {}
            home_wins = int(ht.get("wins", 0)); draws = int(ht.get("draws", 0)); away_wins = int(at.get("wins", 0))
            total_from_block = int(h2h_block.get("numberOfMatches", home_wins + draws + away_wins))
        except:
            pass
    total = len(meetings) if len(meetings) > 0 else total_from_block
    out = {"home": home_name, "away": away_name, "total": total, "total_meetings": total, "home_wins": home_wins, "draws": draws, "away_wins": away_wins, "home_goals": home_goals, "away_goals": away_goals, "btts": btts, "btts_count": btts, "over25": over25, "over_25": over25, "over_25_count": over25, "meetings": meetings}
    if meetings:
        cache_set(key, out)
    return out
