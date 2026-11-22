# Poisson = turn average goals into chances
# Example: average 1.8 goals -> chance of scoring 2 goals = ?

import math
from typing import Dict, Tuple

def poisson_probability(goals: int, avg_goals: float) -> float:
    # Chance of scoring exactly `goals` goals when average is `avg_goals`
    if avg_goals <= 0:
        return 1.0 if goals == 0 else 0.0
    return (math.exp(-avg_goals) * (avg_goals ** goals)) / math.factorial(goals)

def build_scoreline_matrix(exp_home: float, exp_away: float, max_goals: int = 4) -> Dict[Tuple[int, int], float]:
    # Make a table of all scores from 0-0 to 4-4
    # Returns: {(2, 1): 0.12, ...} means 2-1 is 12%
    matrix = {}
    total = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_probability(h, exp_home) * poisson_probability(a, exp_away)
            # Dixon-Coles small correction: low scores are a bit less likely
            if h == 0 and a == 0:
                p *= 0.95
            if h == 1 and a == 0:
                p *= 1.02
            if h == 0 and a == 1:
                p *= 1.02
            if h == 1 and a == 1:
                p *= 0.98
            matrix[(h, a)] = p
            total += p
    # Make sure all chances add up to 100%
    for k in matrix:
        matrix[k] = matrix[k] / total
    return matrix

def matrix_to_1x2(matrix: Dict[Tuple[int, int], float]) -> Tuple[float, float, float]:
    home = sum(p for (h, a), p in matrix.items() if h > a)
    draw = sum(p for (h, a), p in matrix.items() if h == a)
    away = sum(p for (h, a), p in matrix.items() if h < a)
    return home, draw, away

def matrix_to_over_under(matrix: Dict[Tuple[int, int], float]) -> Tuple[float, float]:
    over = sum(p for (h, a), p in matrix.items() if h + a > 2.5)
    under = 1.0 - over
    return over, under

def matrix_to_btts(matrix: Dict[Tuple[int, int], float]) -> Tuple[float, float]:
    yes = sum(p for (h, a), p in matrix.items() if h > 0 and a > 0)
    no = 1.0 - yes
    return yes, no
