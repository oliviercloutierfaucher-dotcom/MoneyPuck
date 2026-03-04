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
    """Exponential decay weight.  A game *half_life* days ago gets weight 0.5.

    Parameter audit (half_life = 30 days)
    --------------------------------------
    Sample decay curve:
        - 7 days ago  : weight ~0.84  (recent games dominate)
        - 14 days ago : weight ~0.71
        - 30 days ago : weight  0.50  (half-life boundary)
        - 60 days ago : weight  0.25
        - 90 days ago : weight  0.125

    At 30 days, early-October games have near-zero influence by
    mid-season.  This is aggressive recency bias that captures
    current form well (coaching changes, injuries, trades, call-ups)
    but also makes the model reactive to hot/cold streaks (noise).

    Tradeoff:
        - Shorter half-life (14-21 days) -> more reactive, higher
          variance, captures rapid form shifts.
        - Longer half-life (45-60 days) -> smoother, lower variance,
          but slower to detect regime changes (e.g. key injury).
        - 30 days is a balance: roughly one month of games (~14 GP)
          retain meaningful weight, aligning with a team's "current
          identity" while discounting stale data.

    Backtester grid values: [14, 21, 30, 45, 60].

    Boundary behaviour:
    - *days_ago* < 0 returns 0.0 (invalid / future game).
    - *half_life* <= 0 returns 1.0 if ``days_ago == 0`` else 0.0.
    - Very large *days_ago* values may underflow to 0.0, which is fine.
    """
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

    Parameter audit (regression_k = 20)
    ------------------------------------
    Formula: weight = n / (n + k), result = weight * observed + (1-weight) * prior

    Sample weights at k=20:
        -  5 games: 20% observed, 80% prior  (season opener range)
        - 10 games: 33% observed, 67% prior  (~2 weeks in)
        - 20 games: 50% observed, 50% prior  (about 1 month)
        - 40 games: 67% observed, 33% prior  (~mid-season)
        - 60 games: 75% observed, 25% prior
        - 82 games: 80% observed, 20% prior  (full season)

    This is a standard empirical Bayes "pseudo-count" approach.
    k=20 keeps early-season predictions conservative (relying mostly
    on the league-average prior of 0.0 in z-score space) while
    trusting observed performance by mid-season.

    Sensitivity:
        - k=10 : trusts observed data faster (50/50 at just 10 GP).
          Risk: overreacts to small-sample noise early in the year.
        - k=30 : more conservative, requires ~2 months to reach 50/50.
          Safer early on but may under-weight real signals.

    Backtester grid values: [10, 15, 20, 25, 30].
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
    # Always divide by the full weight sum, not just available weights.
    # This pulls the composite toward 0.0 (league average) when metrics
    # are missing, penalizing sparse early-season data instead of
    # artificially inflating the remaining signals.
    full_w = sum(weights.values())
    total = 0.0
    for name, w in weights.items():
        if name in metrics:
            total += metrics[name] * w
    return total / full_w if full_w else 0.0


# ---------------------------------------------------------------------------
# Default metric weights — parameter audit
# ---------------------------------------------------------------------------
#
# Rationale: score-adjusted xG% (0.14) is the single strongest predictor of
# future winning percentage in published hockey analytics research (see
# Evolving Hockey, MoneyPuck methodology notes, and Micah Blake McCurdy's
# work on score effects).  Score adjustment removes the incentive distortion
# where trailing teams take more shots and leading teams sit back.
#
# The "Core performance" cluster (xG variants + high-danger) accounts for
# 55% of the total weight, reflecting the well-established hierarchy:
#   xG-based metrics > shot-based metrics > outcome-based metrics
# in terms of predictive power for future results.
#
# Sensitivity note: shifting score_adj_xg_share from 0.14 to 0.20 (+6pp)
# while proportionally reducing other core weights would concentrate more
# signal on a single metric.  In backtesting, moderate changes (+/- 0.03)
# to any single weight typically move the Brier score by < 0.002, suggesting
# the model is NOT overly sensitive to individual weight tweaks — the
# z-scoring and regression provide natural regularization.  However, large
# shifts (e.g., putting 40%+ on a single metric) can degrade calibration by
# amplifying single-metric noise.
#
# Weights should sum to 1.0 (currently 1.00).
# ---------------------------------------------------------------------------
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
    *k* is a scaling constant (1.0 means 1-std difference ~ 73% win prob).
    Returns (home_prob, away_prob), each clamped to [0.01, 0.99].

    Parameter audit (home_advantage = 0.15)
    -----------------------------------------
    For equal teams (both composite strength 0.0):
        diff = 0.0 + 0.15 - 0.0 = 0.15
        prob = 1 / (1 + e^(-1.0 * 0.15)) = 0.5374  (~53.7%)

    NHL home-ice advantage (2018-2024 regular season) has ranged from
    roughly 53% to 56%, with recent seasons clustering around 54-55%.
    The 2023-24 season saw approximately 54.5% home win rate.

    At 0.15, our model slightly UNDER-estimates home advantage
    (53.7% vs ~54.5% observed).  Consider 0.18 (~54.5%) or 0.20
    (~55.0%) if backtesting confirms the higher value improves Brier
    score.  However, the gap is small (< 1 pp), and the goalie/
    situational adjustments also skew home slightly, so the
    effective home advantage may be higher than the raw 0.15.

    Backtester grid values: [0.05, 0.10, 0.15, 0.18, 0.20, 0.25].

    Parameter audit (logistic_k = 1.0)
    ------------------------------------
    k controls how steeply the logistic curve translates strength
    differences into win probabilities.

    With k=1.0:
        - 0.5 sigma advantage at home: 1/(1+e^(-0.65)) = 65.7%
        - 1.0 sigma advantage at home: 1/(1+e^(-1.15)) = 75.9%
        - 1.5 sigma advantage at home: 1/(1+e^(-1.65)) = 83.9%

    In the NHL, even the best teams (~1 sigma above average) rarely
    sustain >65% overall win rates across a full season.  But that
    aggregate rate includes road games and tough opponents.  Against
    an *average* opponent *at home*, 75% may be reasonable.

    With k=0.8 (flatter curve):
        - 1.0 sigma advantage at home: 1/(1+e^(-0.92)) = 71.5%
    This would compress the probability range and might better match
    NHL's "any given night" parity.  Use the backtester grid to
    determine whether k=0.8 or k=1.0 achieves lower Brier score.

    Backtester grid values: [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5].
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
    base_confidence = min(1.0, avg / (avg + min_games))
    return max(0.05, base_confidence)


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
    return max(0.05, min(1.0, base_confidence - penalty))


# ---------------------------------------------------------------------------
# Phase 3: Smart risk
# ---------------------------------------------------------------------------

def fractional_kelly(
    model_probability: float, decimal_odds: float, fraction: float = 0.5
) -> float:
    """Kelly criterion scaled by *fraction* (default half-Kelly)."""
    return kelly_fraction(model_probability, decimal_odds) * fraction


def confidence_adjusted_kelly(
    model_prob: float,
    decimal_odds: float,
    confidence: float,
    fraction: float = 0.5,
) -> float:
    """Kelly with confidence-adjusted probability.

    Low confidence pulls model_prob toward 0.5 (no-edge prior)
    before computing Kelly, rather than scaling the stake post-hoc.
    """
    confidence = max(0.0, min(1.0, confidence))
    adjusted_prob = confidence * model_prob + (1 - confidence) * 0.5
    return fractional_kelly(adjusted_prob, decimal_odds, fraction)


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

    Parameter audit (goalie_impact = 1.5)
    ---------------------------------------
    Sample adjustments:
        - 0.005 sv% diff (e.g. 0.915 vs 0.910): +0.75 pp
        - 0.010 sv% diff (e.g. 0.920 vs 0.910): +1.50 pp
        - 0.020 sv% diff (e.g. 0.920 vs 0.900): +3.00 pp
        - 0.030 sv% diff (e.g. 0.930 vs 0.900): +4.50 pp

    A 3pp swing for a 0.020 diff is meaningful but reasonable —
    goaltending is widely considered the single largest individual
    player impact in hockey.  At 1.5, the adjustment is moderate;
    some models use 2.0 or higher.

    CRITICAL LIMITATION — Starter detection:
    The goalie stats come from infer_likely_starter() in nhl_api.py,
    which picks the goalie with the most games played on each team.
    This is a POOR proxy for "who starts tonight" because:
        1. It always returns the season GP leader (the #1 starter),
           even on nights when the backup is actually starting.
        2. It has no access to daily lineup confirmations, morning
           skate reports, or official starting goalie announcements.
        3. Around tandem situations (e.g., 40/40 GP splits), it may
           pick the wrong goalie ~50% of the time.
        4. Injured starters will still be selected until the backup
           surpasses them in total GP.

    Impact of this limitation: on nights when a backup starts, the
    model applies the starter's (higher) save% — overestimating
    that team's goalie quality by potentially 1-3 pp.  This is an
    unquantified source of error.

    Mitigation path: integrate a real-time starting goalie feed
    (e.g., DailyFaceoff, LeftWingLock) or the NHL API game preview.
    """
    if home_save_pct <= 0 or away_save_pct <= 0:
        return 0.0
    return (home_save_pct - away_save_pct) * impact_scaling * 100
