# Main prediction engine - FIXED to handle dict stats from real API
from typing import Dict, List, Tuple
from .schemas import PredictionResult, ScorelineProb
from .elo import elo_to_goals_adjustment
from .poisson import build_scoreline_matrix, matrix_to_1x2, matrix_to_over_under, matrix_to_btts

def _v(obj, key, default=0.0):
    # Helper: works whether obj is a dict {"npxg": 1.4} or an object stats.npxg
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def weighted_npxg(last_matches: List, is_home: bool = True) -> Tuple[float, float]:
    total_w = 0.0
    sum_for = 0.0
    sum_against = 0.0
    for i, m in enumerate((last_matches or [])[:8]):
        w = 0.85 ** i
        if _v(m, "minutes_leading_by_2plus", 0) > 20:
            w *= 0.8
        npxg_for = min(_v(m, "npxg_for", 1.4), 3.5)
        npxg_against = min(_v(m, "npxg_against", 1.4), 3.5)
        if _v(m, "red_card", False):
            w *= 0.7
        sum_for += w * npxg_for
        sum_against += w * npxg_against
        total_w += w
    if total_w == 0:
        return 1.4, 1.4
    return sum_for / total_w, sum_against / total_w

def calculate_expected_goals(home_stats, away_stats, context: Dict | None = None) -> Tuple[float, float]:
    ctx = context or {}
    home_w_for, home_w_against = weighted_npxg(_v(home_stats, "last_matches", []))
    away_w_for, away_w_against = weighted_npxg(_v(away_stats, "last_matches", []))
    home_attack = 0.6 * home_w_for + 0.4 * _v(home_stats, "npxg", 1.4)
    home_defense = 0.6 * home_w_against + 0.4 * _v(home_stats, "npxga", 1.4)
    away_attack = 0.6 * away_w_for + 0.4 * _v(away_stats, "npxg", 1.4)
    away_defense = 0.6 * away_w_against + 0.4 * _v(away_stats, "npxga", 1.4)
    home_press = max(-0.1, min(0.1, (12.0 - _v(home_stats, "ppda", 11.5)) * 0.02))
    away_press = max(-0.1, min(0.1, (12.0 - _v(away_stats, "ppda", 11.5)) * 0.02))
    home_tilt = (_v(home_stats, "field_tilt", 50) - 50) / 100.0 * 0.3
    away_tilt = (_v(away_stats, "field_tilt", 50) - 50) / 100.0 * 0.3
    home_set = (_v(home_stats, "set_piece_xg", 0.35) - _v(home_stats, "set_piece_xga", 0.35)) * 0.5
    away_set = (_v(away_stats, "set_piece_xg", 0.35) - _v(away_stats, "set_piece_xga", 0.35)) * 0.5
    exp_home = (home_attack + away_defense) / 2.0
    exp_away = (away_attack + home_defense) / 2.0
    exp_home += home_press + home_tilt + home_set
    exp_away += away_press + away_tilt + away_set
    elo_home = 1500 + (_v(home_stats, "npxg", 1.4) - _v(home_stats, "npxga", 1.4)) * 80
    elo_away = 1500 + (_v(away_stats, "npxg", 1.4) - _v(away_stats, "npxga", 1.4)) * 80
    exp_home += elo_to_goals_adjustment(elo_home - elo_away)
    exp_away += elo_to_goals_adjustment(elo_away - elo_home)
    exp_home += 0.25
    if ctx.get("home_rest_days", 7) < 3:
        exp_home -= 0.08
    if ctx.get("away_rest_days", 7) < 3:
        exp_away -= 0.08
    exp_home -= ctx.get("home_missing_key", 0) * 0.07
    exp_away -= ctx.get("away_missing_key", 0) * 0.07
    exp_home -= ctx.get("home_missing_gk", 0) * 0.08
    exp_away -= ctx.get("away_missing_gk", 0) * 0.08
    exp_home += ctx.get("ref_penalty_rate", 0.0) * 0.05
    exp_away += ctx.get("ref_penalty_rate", 0.0) * 0.05
    exp_home += ctx.get("home_motivation", 0.0) * 0.05
    exp_away += ctx.get("away_motivation", 0.0) * 0.05
    h2h_w = ctx.get("h2h_weight", 0.0)
    if h2h_w > 0:
        exp_home = (1 - h2h_w) * exp_home + h2h_w * ctx.get("h2h_home_xg", exp_home)
        exp_away = (1 - h2h_w) * exp_away + h2h_w * ctx.get("h2h_away_xg", exp_away)
    exp_home = max(0.2, min(3.8, exp_home))
    exp_away = max(0.2, min(3.8, exp_away))
    return exp_home, exp_away

def predict(fixture_id: str, home_team: str, away_team: str, home_stats, away_stats, context: Dict | None = None) -> PredictionResult:
    exp_home, exp_away = calculate_expected_goals(home_stats, away_stats, context)
    matrix = build_scoreline_matrix(exp_home, exp_away, max_goals=4)
    home_win, draw, away_win = matrix_to_1x2(matrix)
    over, under = matrix_to_over_under(matrix)
    btts_yes, btts_no = matrix_to_btts(matrix)
    scorelines = [ScorelineProb(home_goals=h, away_goals=a, probability=p) for (h, a), p in sorted(matrix.items(), key=lambda x: -x[1])]
    most = scorelines[0]
    return PredictionResult(
        fixture_id=fixture_id,
        home_team=home_team,
        away_team=away_team,
        home_win=home_win,
        draw=draw,
        away_win=away_win,
        over_25=over,
        under_25=under,
        btts_yes=btts_yes,
        btts_no=btts_no,
        expected_home_goals=exp_home,
        expected_away_goals=exp_away,
        most_likely_score=f"{most.home_goals}-{most.away_goals}",
        scorelines=scorelines,
    )
