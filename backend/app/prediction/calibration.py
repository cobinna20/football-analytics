# Calibration = compare model vs bookmakers
# De-vig = remove bookmaker margin to get true market chance

from typing import Tuple

def devig_1x2(home_odds: float, draw_odds: float, away_odds: float) -> Tuple[float, float, float]:
    # 1/odds = implied chance including margin
    inv_h = 1.0 / home_odds
    inv_d = 1.0 / draw_odds
    inv_a = 1.0 / away_odds
    total = inv_h + inv_d + inv_a
    return inv_h / total, inv_d / total, inv_a / total

def model_edge(model_prob: float, market_prob: float) -> float:
    # Positive = model thinks it is more likely than market
    return model_prob - market_prob

def brier_score(predicted_probs: list[float], actual_index: int) -> float:
    # 0 = perfect, 2 = worst. Lower is better.
    s = 0.0
    for i, p in enumerate(predicted_probs):
        actual = 1.0 if i == actual_index else 0.0
        s += (p - actual) ** 2
    return s

def log_loss(predicted_probs: list[float], actual_index: int) -> float:
    import math
    p = max(0.001, min(0.999, predicted_probs[actual_index]))
    return -math.log(p)
