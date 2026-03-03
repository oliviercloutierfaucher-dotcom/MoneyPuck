from __future__ import annotations

import math
from datetime import datetime


# ---------------------------------------------------------------------------
# Odds conversion (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# EV & Kelly (base versions unchanged)
# ---------------------------------------------------------------------------

def expected_value_per_dollar(model_probability: float, decimal_odds: float) -> float:
    model_probability = _clamp_probability(model_probability)
    if decimal_odds <= 1.0:
        return 0.0
    win_profit = decimal_odds - 1
    return model_probability * win_profit - (1 - model_probability)


def kelly_fraction(model_probability: float, decimal_odds: float) -> float:
    """Kelly criterion fraction; clipped at zero for no-bet outcomes."""
    model_probability = _clamp_probability(model_probability)
    b = decimal_odds - 1
    q = 1 - model_probability
    if b <= 0:
        return 0.0
    fraction = ((b * model_probability) - q) / b
    return max(0.0, fraction)


# ---------------------------------------------------------------------------
# Phase 1: Team strength utilities
# ---------------------------------------------------------------------------

def _clamp_probability(p: float) -> float:
    """Clamp a probability to [0.0, 1.0]."""
    return max(0.0, min(1.0, p))


def exponential_decay_weight(days_ago: float, half_life: float = 30.0) -> float:
    """Exponential decay weight.  A game *half_life* days ago gets weight 0.5."""
    if days_ago < 0:
        return 0.0
    if half_life <= 0:
        return 1.0 if days_ago == 0 else 0.0
    return math.exp(-math.log(2) * days_ago / half_life)


def regress_to_mean(
    observed: float, n: int, k: int = 20, prior: float = 0.5
) -> float:
    """Bayesian shrinkage toward *prior*.

    At *k* observations the weight is 50/50 between observed and prior.
    """
    if n + k == 0:
        return prior
    weight = n / (n + k)
    return weight * observed + (1 - weight) * prior


def composite_strength(
    metrics: dict[str, float],
    weights: dict[str, float] | None = None,
) -> float:
    """Weighted sum of z-scored metric values.

    *metrics* maps metric names to z-score values.
    *weights* maps the same names to importance weights (should sum to ~1).
    """
    if weights is None:
        weights = DEFAULT_METRIC_WEIGHTS
    total_w = 0.0
    total = 0.0
    for name, w in weights.items():
        if name in metrics:
            total += metrics[name] * w
            total_w += w
    return total / total_w if total_w else 0.0


DEFAULT_METRIC_WEIGHTS: dict[str, float] = {
    # Core performance (55%)
    "xg_share": 0.12,
    "score_adj_xg_share": 0.14,     # Score-adjusted is more predictive than raw xG
    "flurry_adj_xg_share": 0.10,    # Penalizes rebound shot clusters
    "high_danger_share": 0.10,
    "hd_xg_share": 0.09,            # High-danger xG share
    # Possession & shot quality (18%)
    "corsi_share": 0.06,
    "fenwick_share": 0.06,
    "md_xg_share": 0.06,            # Medium-danger quality
    # Execution (12%)
    "shooting_pct": 0.06,
    "save_pct": 0.06,
    # Special teams (6%)
    "pp_xg_per_60": 0.03,
    "pk_xg_against_per_60": 0.03,
    # Puck management (9%)
    "rebound_control": 0.03,        # Offensive rebound creation
    "faceoff_pct": 0.03,
    "takeaway_ratio": 0.02,
    "dzone_giveaway_rate": 0.01,    # D-zone turnovers (inverted: lower = better)
}


def days_between(date_a: str, date_b: str) -> int:
    """Absolute number of days between two ISO-format date strings."""
    fmt = "%Y-%m-%d"
    da = datetime.strptime(date_a[:10], fmt)
    db = datetime.strptime(date_b[:10], fmt)
    return abs((db - da).days)


# ---------------------------------------------------------------------------
# Phase 2: Win probability
# ---------------------------------------------------------------------------

def logistic_win_probability(
    home_strength: float,
    away_strength: float,
    home_advantage: float = 0.15,
    k: float = 1.0,
) -> tuple[float, float]:
    """Logistic model mapping composite-strength difference to win probability.

    *home_advantage* is added to the home side in z-score space.
    *k* is a scaling constant (1.0 means 1-std difference ≈ 73% win prob).
    Returns (home_prob, away_prob), each clamped to [0.01, 0.99].
    """
    diff = (home_strength + home_advantage) - away_strength
    # Guard against overflow for extreme differences
    exponent = -k * diff
    exponent = max(-500, min(500, exponent))
    home_prob = 1.0 / (1.0 + math.exp(exponent))
    # Clamp to prevent degenerate probabilities
    home_prob = max(0.01, min(0.99, home_prob))
    return home_prob, 1.0 - home_prob


def prediction_confidence(
    games_a: int, games_b: int, min_games: int = 15
) -> float:
    """0-1 confidence score based on sample sizes of both teams.

    The score ramps from 0 to 1 as both teams accumulate games.
    At *min_games* per team the confidence is 50%; at 2× *min_games*
    it reaches 67%.
    """
    avg = (games_a + games_b) / 2.0
    return min(1.0, avg / (avg + min_games))


def edge_adjusted_confidence(
    base_confidence: float,
    edge_pp: float,
    max_edge_penalty: float = 0.15,
    edge_threshold: float = 8.0,
) -> float:
    """Reduce confidence when the claimed edge is suspiciously large.

    Very large edges (>8pp) often indicate stale lines or model noise
    rather than genuine mispricing.  This applies a graduated penalty:
    an edge of 8pp gets no penalty, 16pp loses ~7.5% confidence, etc.

    Returns adjusted confidence clamped to [0, 1].
    """
    excess = max(0.0, abs(edge_pp) - edge_threshold)
    # Penalty scales linearly: every 8pp above threshold costs max_edge_penalty
    penalty = min(max_edge_penalty, excess / edge_threshold * max_edge_penalty)
    return max(0.0, min(1.0, base_confidence - penalty))


# ---------------------------------------------------------------------------
# Phase 3: Smart risk
# ---------------------------------------------------------------------------

def fractional_kelly(
    model_probability: float, decimal_odds: float, fraction: float = 0.5
) -> float:
    """Kelly criterion scaled by *fraction* (default half-Kelly)."""
    return kelly_fraction(model_probability, decimal_odds) * fraction


def confidence_adjusted_kelly(
    model_probability: float,
    decimal_odds: float,
    confidence: float,
    fraction: float = 0.5,
) -> float:
    """Kelly scaled by both fractional multiplier and model confidence."""
    confidence = _clamp_probability(confidence)
    return fractional_kelly(model_probability, decimal_odds, fraction) * confidence


# ---------------------------------------------------------------------------
# Goalie matchup adjustment
# ---------------------------------------------------------------------------

LEAGUE_AVG_SAVE_PCT = 0.905


def goalie_matchup_adjustment(
    home_save_pct: float,
    away_save_pct: float,
    impact_scaling: float = 1.5,
) -> float:
    """Win probability adjustment based on goalie save-percentage differential.

    A 0.01 save% difference translates to roughly *impact_scaling* percentage
    points of win probability.  Default 1.5 means a starter with 0.920 sv%
    vs. a backup with 0.900 sv% gives the home team +3pp.

    Returns adjustment from the **home team's perspective** (positive = home
    team has the better goalie).
    """
    if home_save_pct <= 0 or away_save_pct <= 0:
        return 0.0
    return (home_save_pct - away_save_pct) * impact_scaling * 100
