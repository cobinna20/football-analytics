# Elo = points for each team
# Win against strong team = gain many points
# Lose to weak team = lose many points

def expected_score(rating_a: float, rating_b: float) -> float:
    # Chance team A beats team B, based on points
    # Returns a number from 0 to 1. 0.5 means equal.
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

def update_elo(rating_a: float, rating_b: float, result_a: float, k: float = 20.0) -> tuple[float, float]:
    # result_a: 1.0 = A won, 0.5 = draw, 0.0 = A lost
    # k = how fast points move. 20 is normal.
    exp_a = expected_score(rating_a, rating_b)
    exp_b = 1.0 - exp_a
    new_a = rating_a + k * (result_a - exp_a)
    new_b = rating_b + k * ((1.0 - result_a) - exp_b)
    return new_a, new_b

def elo_to_goals_adjustment(rating_diff: float) -> float:
    # Turn Elo difference into extra goals
    # 100 points difference = about 0.15 extra goals
    return max(-0.5, min(0.5, rating_diff / 100.0 * 0.15))
