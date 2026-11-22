# Main prediction engine
# Tier 1: Recent form 45% - Tier 2: Situation 25% - Tier 3: Small details 15% - Tier 4: H2H + Market 15%

from typing import Dict, List, Tuple
from .schemas import PredictionResult, ScorelineProb
from .elo import elo_to_goals_adjustment
from .poisson import build_scoreline_matrix, matrix_to_1x2, matrix_to_over_under, matrix_to_btts

def weighted_npxg(last_matches: List, is_home: bool = True) -> Tuple[float, float]:
    # Recent matches count more. Last match weight = 1.0, older = 0.85, 0.72, etc.
    # Cap crazy games and discount garbage time when leading by 2+.
    total_w = 0.0
    sum_for = 0.0
    sum_against = 0.0
    for i, m in enumerate(last_matches[:8]):
        w = 0.85 ** i
        # Game-state filter: if team led by 2+ for long, that match is less useful
        if m.minutes_leading_by_2plus > 20:
            w *= 0.8
        # Outlier capping: no single match can be more than 3.5 xG
        npxg_for = min(m.npxg_for, 3.5)
        npxg_against = min(m.npxg_against, 3.5)
        # Red card game is less useful
        if m.red_card:
            w *= 0.7
        sum_for += w * npxg_for
        sum_against += w * npxg_against
        total_w += w
    if total_w == 0:
        return 1.4, 1.4
    return sum_for / total_w, sum_against / total_w

def calculate_expected_goals(home_stats, away_stats, context: Dict | None = None) -> Tuple[float, float]:
    ctx = context or {}
    # Tier 1: Base from weighted recent form + season npxG
    home_w_for, home_w_against = weighted_npxg(home_stats.last_matches)
    away_w_for, away_w_against = weighted_npxg(away_stats.last_matches)
    home_attack = 0.6 * home_w_for + 0.4 * home_stats.npxg
    home_defense = 0.6 * home_w_against + 0.4 * home_stats.npxga
    away_attack = 0.6 * away_w_for + 0.4 * away_stats.npxg
    away_defense = 0.6 * away_w_against + 0.4 * away_stats.npxga

    # PPDA and Field Tilt adjust attack: lower PPDA = more pressing = more attack
    home_press = max(-0.1, min(0.1, (12.0 - home_stats.ppda) * 0.02))
    away_press = max(-0.1, min(0.1, (12.0 - away_stats.ppda) * 0.02))
    home_tilt = (home_stats.field_tilt - 50) / 100.0 * 0.3
    away_tilt = (away_stats.field_tilt - 50) / 100.0 * 0.3

    # Set-piece edge
    home_set = (home_stats.set_piece_xg - home_stats.set_piece_xga) * 0.5
    away_set = (away_stats.set_piece_xg - away_stats.set_piece_xga) * 0.5

    # Base expected goals: attack of one vs defense of other
    exp_home = (home_attack + away_defense) / 2.0
    exp_away = (away_attack + home_defense) / 2.0
    exp_home += home_press + home_tilt + home_set
    exp_away += away_press + away_tilt + away_set

    # Elo adjustment from npxG difference
    elo_home = 1500 + (home_stats.npxg - home_stats.npxga) * 80
    elo_away = 1500 + (away_stats.npxg - away_stats.npxga) * 80
    exp_home += elo_to_goals_adjustment(elo_home - elo_away)
    exp_away += elo_to_goals_adjustment(elo_away - elo_home)

    # Tier 2: Home advantage + rest + missing players
    exp_home += 0.25  # Home advantage
    home_rest = ctx.get("home_rest_days", 7)
    away_rest = ctx.get("away_rest_days", 7)
    if home_rest < 3:
        exp_home -= 0.08
    if away_rest < 3:
        exp_away -= 0.08
    exp_home -= ctx.get("home_missing_key", 0) * 0.07
    exp_away -= ctx.get("away_missing_key", 0) * 0.07
    exp_home -= ctx.get("home_missing_gk", 0) * 0.08
    exp_away -= ctx.get("away_missing_gk", 0) * 0.08

    # Tier 3: Referee penalty rate, weather, motivation
    exp_home += ctx.get("ref_penalty_rate", 0.0) * 0.05
    exp_away += ctx.get("ref_penalty_rate", 0.0) * 0.05
    exp_home += ctx.get("home_motivation", 0.0) * 0.05
    exp_away += ctx.get("away_motivation", 0.0) * 0.05

    # Tier 4: H2H filter - only if same managers and recent, else weight = 0
    h2h_w = ctx.get("h2h_weight", 0.0)
    if h2h_w > 0:
        h2h_home_xg = ctx.get("h2h_home_xg", exp_home)
        h2h_away_xg = ctx.get("h2h_away_xg", exp_away)
        exp_home = (1 - h2h_w) * exp_home + h2h_w * h2h_home_xg
        exp_away = (1 - h2h_w) * exp_away + h2h_w * h2h_away_xg

    # Keep in sane range
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
