from __future__ import annotations


def american_to_decimal(american_odds: int) -> float:
    if american_odds == 0:
        raise ValueError("American odds cannot be 0")
    if american_odds > 0:
        return 1 + american_odds / 100
    return 1 + 100 / abs(american_odds)


def american_to_implied_probability(american_odds: int) -> float:
    if american_odds == 0:
        raise ValueError("American odds cannot be 0")
    if american_odds > 0:
        return 100 / (american_odds + 100)
    return abs(american_odds) / (abs(american_odds) + 100)


def expected_value_per_dollar(model_probability: float, decimal_odds: float) -> float:
    win_profit = decimal_odds - 1
    return model_probability * win_profit - (1 - model_probability)


def kelly_fraction(model_probability: float, decimal_odds: float) -> float:
    """Kelly criterion fraction; clipped at zero for no-bet outcomes."""
    b = decimal_odds - 1
    q = 1 - model_probability
    if b <= 0:
        return 0.0
    fraction = ((b * model_probability) - q) / b
    return max(0.0, fraction)
