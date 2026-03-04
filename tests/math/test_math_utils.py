"""Comprehensive tests for app.math.math_utils.

Covers every public function with happy-path, edge-case, numerical-stability,
and consistency checks.  Target: 50+ individual test cases.
"""

import math
import pytest

from app.math.math_utils import (
    american_to_decimal,
    american_to_implied_probability,
    composite_strength,
    confidence_adjusted_kelly,
    days_between,
    edge_adjusted_confidence,
    expected_value_per_dollar,
    exponential_decay_weight,
    fractional_kelly,
    goalie_matchup_adjustment,
    kelly_fraction,
    logistic_win_probability,
    prediction_confidence,
    regress_to_mean,
    _clamp_probability,
    DEFAULT_METRIC_WEIGHTS,
)


# ===================================================================
# american_to_decimal
# ===================================================================

class TestAmericanToDecimal:
    """Tests for american_to_decimal()."""

    def test_positive_150(self):
        assert round(american_to_decimal(150), 2) == 2.50

    def test_positive_100(self):
        assert round(american_to_decimal(100), 2) == 2.00

    def test_positive_250(self):
        assert round(american_to_decimal(250), 2) == 3.50

    def test_negative_110(self):
        assert abs(american_to_decimal(-110) - 1.9091) < 0.001

    def test_negative_200(self):
        assert round(american_to_decimal(-200), 2) == 1.50

    def test_negative_100(self):
        assert round(american_to_decimal(-100), 2) == 2.00

    def test_negative_300(self):
        assert abs(american_to_decimal(-300) - 1.3333) < 0.001

    def test_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="cannot be 0"):
            american_to_decimal(0)

    def test_extreme_positive(self):
        # +50000 -> 1 + 50000/100 = 501.0
        assert american_to_decimal(50000) == 501.0

    def test_extreme_negative(self):
        # -50000 -> 1 + 100/50000 = 1.002
        assert abs(american_to_decimal(-50000) - 1.002) < 0.0001

    def test_symmetry_positive_negative_100(self):
        """Both +100 and -100 should give decimal odds of 2.00 (even money)."""
        assert american_to_decimal(100) == american_to_decimal(-100)


# ===================================================================
# american_to_implied_probability
# ===================================================================

class TestAmericanToImpliedProbability:
    """Tests for american_to_implied_probability()."""

    def test_positive_150(self):
        assert abs(american_to_implied_probability(150) - 0.40) < 0.001

    def test_negative_150(self):
        assert abs(american_to_implied_probability(-150) - 0.60) < 0.001

    def test_negative_110(self):
        assert abs(american_to_implied_probability(-110) - 0.5238) < 0.001

    def test_positive_100(self):
        assert abs(american_to_implied_probability(100) - 0.50) < 0.001

    def test_negative_100(self):
        assert abs(american_to_implied_probability(-100) - 0.50) < 0.001

    def test_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="cannot be 0"):
            american_to_implied_probability(0)

    def test_extreme_positive_50000(self):
        # 100 / (50000 + 100) = 100/50100 ~ 0.001996
        result = american_to_implied_probability(50000)
        assert abs(result - 0.001996) < 0.0001

    def test_extreme_negative_50000(self):
        # 50000 / (50000 + 100) = 50000/50100 ~ 0.998
        result = american_to_implied_probability(-50000)
        assert abs(result - 0.998) < 0.001

    def test_vig_pair_sums_above_one(self):
        """A vig pair like -110/-110 should have implied probs summing > 1.0."""
        h = american_to_implied_probability(-110)
        a = american_to_implied_probability(-110)
        assert h + a > 1.0  # vig margin

    def test_fair_pair_sums_to_one(self):
        """An even-money pair (+100/+100) should sum to exactly 1.0."""
        h = american_to_implied_probability(100)
        a = american_to_implied_probability(100)
        assert abs(h + a - 1.0) < 0.0001

    def test_implied_probability_range(self):
        """Implied probability should always be in (0, 1)."""
        for odds in [100, -100, 200, -200, 500, -500, 10000, -10000]:
            p = american_to_implied_probability(odds)
            assert 0 < p < 1, f"Odds {odds} gave probability {p}"


# ===================================================================
# expected_value_per_dollar
# ===================================================================

class TestExpectedValuePerDollar:
    """Tests for expected_value_per_dollar()."""

    def test_positive_ev(self):
        # p=0.55, d=1.91 -> 0.55*0.91 - 0.45 = 0.0505
        ev = expected_value_per_dollar(0.55, 1.91)
        assert abs(ev - 0.0505) < 0.001

    def test_fair_bet_2x(self):
        # p=0.50, d=2.00 -> 0.50*1.00 - 0.50 = 0.0
        ev = expected_value_per_dollar(0.50, 2.00)
        assert abs(ev) < 0.0001

    def test_fair_bet_2_5x(self):
        # p=0.40, d=2.50 -> 0.40*1.50 - 0.60 = 0.0
        ev = expected_value_per_dollar(0.40, 2.50)
        assert abs(ev) < 0.0001

    def test_negative_ev(self):
        # p=0.30, d=2.00 -> 0.30*1.00 - 0.70 = -0.40
        ev = expected_value_per_dollar(0.30, 2.00)
        assert abs(ev - (-0.40)) < 0.001

    def test_certain_win(self):
        # p=1.0 -> EV = 1.0 * (d-1) - 0 = d-1
        ev = expected_value_per_dollar(1.0, 3.0)
        assert abs(ev - 2.0) < 0.0001

    def test_certain_loss(self):
        # p=0.0 -> EV = 0 - 1.0 = -1.0
        ev = expected_value_per_dollar(0.0, 3.0)
        assert abs(ev - (-1.0)) < 0.0001

    def test_decimal_odds_at_boundary(self):
        """decimal_odds <= 1.0 should return 0.0 (no valid bet)."""
        assert expected_value_per_dollar(0.55, 1.0) == 0.0
        assert expected_value_per_dollar(0.55, 0.5) == 0.0

    def test_probability_clamped_above_one(self):
        """Probability > 1.0 should be clamped to 1.0."""
        ev = expected_value_per_dollar(1.5, 2.0)
        # Clamped to 1.0: 1.0*1.0 - 0.0 = 1.0
        assert abs(ev - 1.0) < 0.0001

    def test_probability_clamped_below_zero(self):
        """Probability < 0.0 should be clamped to 0.0."""
        ev = expected_value_per_dollar(-0.5, 2.0)
        # Clamped to 0.0: 0.0*1.0 - 1.0 = -1.0
        assert abs(ev - (-1.0)) < 0.0001

    def test_ev_zero_when_prob_equals_implied(self):
        """EV should be ~0 when model prob equals implied prob."""
        # -110 odds -> implied 0.5238, decimal 1.9091
        implied = american_to_implied_probability(-110)
        dec_odds = american_to_decimal(-110)
        ev = expected_value_per_dollar(implied, dec_odds)
        assert abs(ev) < 0.001


# ===================================================================
# kelly_fraction
# ===================================================================

class TestKellyFraction:
    """Tests for kelly_fraction()."""

    def test_positive_edge(self):
        # p=0.55, d=1.91: f = (0.91*0.55 - 0.45)/0.91 = 0.0555
        f = kelly_fraction(0.55, 1.91)
        assert abs(f - 0.0555) < 0.001

    def test_no_edge_returns_zero(self):
        # p=0.50, d=2.00: (1.0*0.50 - 0.50)/1.0 = 0.0
        f = kelly_fraction(0.50, 2.00)
        assert f == 0.0

    def test_negative_edge_returns_zero(self):
        # p=0.30, d=2.00: (1.0*0.30 - 0.70)/1.0 = -0.40 -> max(0, -0.40) = 0
        f = kelly_fraction(0.30, 2.00)
        assert f == 0.0

    def test_certain_win_all_in(self):
        # p=1.0, d=2.0: (1.0*1.0 - 0.0)/1.0 = 1.0
        f = kelly_fraction(1.0, 2.0)
        assert abs(f - 1.0) < 0.0001

    def test_certain_loss_no_bet(self):
        # p=0.0, d=2.0: (1.0*0.0 - 1.0)/1.0 = -1.0 -> 0.0
        f = kelly_fraction(0.0, 2.0)
        assert f == 0.0

    def test_kelly_zero_for_negative_ev(self):
        """Kelly should be 0.0 whenever EV is non-positive."""
        for p in [0.1, 0.2, 0.3, 0.4]:
            assert kelly_fraction(p, 2.0) == 0.0 or expected_value_per_dollar(p, 2.0) > 0

    def test_decimal_odds_at_or_below_one(self):
        """With b <= 0 (odds <= 1.0), Kelly should return 0.0."""
        assert kelly_fraction(0.90, 1.0) == 0.0
        assert kelly_fraction(0.90, 0.5) == 0.0

    def test_kelly_consistent_with_ev(self):
        """Kelly should be 0 whenever EV is <= 0, and positive when EV > 0."""
        test_cases = [
            (0.55, 1.91),  # positive EV
            (0.50, 2.00),  # zero EV
            (0.30, 2.00),  # negative EV
            (0.60, 1.80),  # slight positive EV
        ]
        for p, d in test_cases:
            ev = expected_value_per_dollar(p, d)
            kf = kelly_fraction(p, d)
            if ev <= 0:
                assert kf == 0.0, f"Kelly > 0 but EV <= 0 for p={p}, d={d}"
            else:
                assert kf > 0.0, f"Kelly == 0 but EV > 0 for p={p}, d={d}"


# ===================================================================
# fractional_kelly
# ===================================================================

class TestFractionalKelly:
    """Tests for fractional_kelly()."""

    def test_half_kelly(self):
        full = kelly_fraction(0.55, 1.91)
        half = fractional_kelly(0.55, 1.91, 0.5)
        assert abs(half - full * 0.5) < 0.0001

    def test_quarter_kelly(self):
        full = kelly_fraction(0.55, 1.91)
        quarter = fractional_kelly(0.55, 1.91, 0.25)
        assert abs(quarter - full * 0.25) < 0.0001

    def test_full_kelly(self):
        full = kelly_fraction(0.55, 1.91)
        full_frac = fractional_kelly(0.55, 1.91, 1.0)
        assert abs(full_frac - full) < 0.0001

    def test_zero_fraction(self):
        result = fractional_kelly(0.55, 1.91, 0.0)
        assert result == 0.0


# ===================================================================
# _clamp_probability
# ===================================================================

class TestClampProbability:
    """Tests for _clamp_probability()."""

    def test_within_range(self):
        assert _clamp_probability(0.5) == 0.5

    def test_at_zero(self):
        assert _clamp_probability(0.0) == 0.0

    def test_at_one(self):
        assert _clamp_probability(1.0) == 1.0

    def test_below_zero(self):
        assert _clamp_probability(-0.5) == 0.0

    def test_above_one(self):
        assert _clamp_probability(1.5) == 1.0


# ===================================================================
# exponential_decay_weight
# ===================================================================

class TestExponentialDecayWeight:
    """Tests for exponential_decay_weight()."""

    def test_zero_days_ago(self):
        """Most recent game should have weight 1.0."""
        assert exponential_decay_weight(0, 30.0) == 1.0

    def test_at_half_life(self):
        """At exactly one half-life, weight should be 0.5."""
        w = exponential_decay_weight(30, 30.0)
        assert abs(w - 0.5) < 0.0001

    def test_at_two_half_lives(self):
        """At two half-lives, weight should be 0.25."""
        w = exponential_decay_weight(60, 30.0)
        assert abs(w - 0.25) < 0.0001

    def test_negative_days_returns_zero(self):
        """Negative days_ago should return 0.0 (invalid input)."""
        assert exponential_decay_weight(-1, 30.0) == 0.0

    def test_zero_half_life_at_zero(self):
        """If half_life <= 0 and days_ago == 0, weight is 1.0."""
        assert exponential_decay_weight(0, 0.0) == 1.0

    def test_zero_half_life_positive_days(self):
        """If half_life <= 0 and days_ago > 0, weight is 0.0."""
        assert exponential_decay_weight(5, 0.0) == 0.0

    def test_very_large_days_ago(self):
        """Very old games should have weight approaching 0."""
        w = exponential_decay_weight(1000, 30.0)
        assert w < 0.001


# ===================================================================
# regress_to_mean
# ===================================================================

class TestRegressToMean:
    """Tests for regress_to_mean()."""

    def test_zero_observations(self):
        """With n=0, should return the prior."""
        assert regress_to_mean(0.80, 0, k=20) == 0.5

    def test_at_k_observations(self):
        """At n=k, weight is 50/50 between observed and prior."""
        result = regress_to_mean(0.80, 20, k=20)
        expected = 0.5 * 0.80 + 0.5 * 0.5  # = 0.65
        assert abs(result - expected) < 0.0001

    def test_very_large_n(self):
        """With very large n, should approach observed value."""
        result = regress_to_mean(0.80, 10000, k=20)
        assert abs(result - 0.80) < 0.001

    def test_custom_prior(self):
        """Should regress toward the specified prior."""
        result = regress_to_mean(0.80, 0, k=20, prior=0.3)
        assert result == 0.3

    def test_n_plus_k_zero(self):
        """Edge case: n=0, k=0 should return prior (avoids division by zero)."""
        assert regress_to_mean(0.80, 0, k=0) == 0.5


# ===================================================================
# composite_strength
# ===================================================================

class TestCompositeStrength:
    """Tests for composite_strength()."""

    def test_all_metrics_at_zero(self):
        """All z-scores at 0 should produce composite of 0."""
        metrics = {k: 0.0 for k in DEFAULT_METRIC_WEIGHTS}
        assert composite_strength(metrics) == 0.0

    def test_all_metrics_at_one(self):
        """All z-scores at 1 should produce weighted sum / total weight."""
        metrics = {k: 1.0 for k in DEFAULT_METRIC_WEIGHTS}
        result = composite_strength(metrics)
        # Sum of weights = 1.0, so result should be ~1.0
        assert abs(result - 1.0) < 0.01

    def test_missing_metrics_penalizes(self):
        """Missing metrics should pull composite toward 0 (league average)."""
        full = {k: 1.0 for k in DEFAULT_METRIC_WEIGHTS}
        partial = {"xg_share": 1.0}
        full_result = composite_strength(full)
        partial_result = composite_strength(partial)
        assert partial_result < full_result

    def test_empty_metrics(self):
        """No metrics at all should return 0.0."""
        assert composite_strength({}) == 0.0

    def test_custom_weights(self):
        """Custom weights should be used instead of defaults."""
        metrics = {"a": 2.0, "b": 1.0}
        weights = {"a": 0.6, "b": 0.4}
        result = composite_strength(metrics, weights)
        expected = (2.0 * 0.6 + 1.0 * 0.4) / 1.0
        assert abs(result - expected) < 0.0001

    def test_weight_normalization(self):
        """Weights that don't sum to 1.0 should still produce correct result."""
        metrics = {"a": 1.0}
        weights = {"a": 2.0, "b": 3.0}
        result = composite_strength(metrics, weights)
        # Only 'a' is available: 1.0 * 2.0 / (2.0 + 3.0) = 0.4
        assert abs(result - 0.4) < 0.0001


# ===================================================================
# days_between
# ===================================================================

class TestDaysBetween:
    """Tests for days_between()."""

    def test_same_day(self):
        assert days_between("2025-01-01", "2025-01-01") == 0

    def test_one_day(self):
        assert days_between("2025-01-01", "2025-01-02") == 1

    def test_reverse_order(self):
        """Order should not matter -- result is absolute."""
        assert days_between("2025-01-10", "2025-01-01") == 9

    def test_handles_timestamp_suffix(self):
        """Should truncate to first 10 characters."""
        assert days_between("2025-01-01T12:00:00Z", "2025-01-03T00:00:00Z") == 2


# ===================================================================
# logistic_win_probability
# ===================================================================

class TestLogisticWinProbability:
    """Tests for logistic_win_probability()."""

    def test_equal_teams_no_home_advantage(self):
        hp, ap = logistic_win_probability(0.0, 0.0, home_advantage=0.0)
        assert abs(hp - 0.5) < 0.001
        assert abs(ap - 0.5) < 0.001

    def test_equal_teams_with_home_advantage(self):
        hp, ap = logistic_win_probability(0.0, 0.0, home_advantage=0.15, k=1.0)
        # diff = 0.15, home_p = 1/(1+exp(-0.15)) ~ 0.5374
        assert abs(hp - 0.5374) < 0.002
        assert hp > 0.5
        assert ap < 0.5

    def test_probabilities_sum_to_one(self):
        hp, ap = logistic_win_probability(0.5, -0.3, 0.15, 1.0)
        assert abs(hp + ap - 1.0) < 0.0001

    def test_strong_home_team(self):
        hp, _ = logistic_win_probability(1.5, -1.0, 0.15, 1.0)
        assert hp > 0.75
        assert hp <= 0.99

    def test_extreme_difference_clamped(self):
        """Extreme differences should be clamped to [0.01, 0.99]."""
        hp, ap = logistic_win_probability(100, -100, 0.0, 1.0)
        assert hp == 0.99
        assert abs(ap - 0.01) < 0.0001

    def test_symmetry(self):
        """Swapping teams with no HA should swap probabilities."""
        h1, a1 = logistic_win_probability(1.0, 0.0, home_advantage=0.0)
        h2, a2 = logistic_win_probability(0.0, 1.0, home_advantage=0.0)
        assert abs(h1 - a2) < 0.001
        assert abs(a1 - h2) < 0.001

    def test_k_scaling(self):
        """Higher k should amplify the strength difference."""
        hp_k1, _ = logistic_win_probability(1.0, 0.0, 0.0, k=1.0)
        hp_k2, _ = logistic_win_probability(1.0, 0.0, 0.0, k=2.0)
        assert hp_k2 > hp_k1  # Higher k magnifies the home advantage

    def test_overflow_protection(self):
        """Should not raise for extreme inputs (exponent clamping)."""
        hp, ap = logistic_win_probability(1e6, -1e6, 0.0, 1.0)
        assert hp == 0.99
        assert abs(ap - 0.01) < 0.0001


# ===================================================================
# prediction_confidence
# ===================================================================

class TestPredictionConfidence:
    """Tests for prediction_confidence()."""

    def test_zero_games(self):
        conf = prediction_confidence(0, 0)
        assert conf == 0.05  # minimum floor

    def test_many_games(self):
        conf = prediction_confidence(60, 60)
        assert conf > 0.75

    def test_at_min_games(self):
        """At avg = min_games (15), confidence = 15/(15+15) = 0.5."""
        conf = prediction_confidence(15, 15, min_games=15)
        assert abs(conf - 0.5) < 0.001

    def test_mixed_games(self):
        # avg = 22.5, conf = 22.5/(22.5+15) = 0.6
        conf = prediction_confidence(5, 40, min_games=15)
        assert 0.55 < conf < 0.65

    def test_minimum_floor(self):
        """Should never drop below 0.05."""
        conf = prediction_confidence(0, 0, min_games=1000)
        assert conf == 0.05


# ===================================================================
# edge_adjusted_confidence
# ===================================================================

class TestEdgeAdjustedConfidence:
    """Tests for edge_adjusted_confidence()."""

    def test_no_penalty_below_threshold(self):
        """Edges below threshold should not be penalized."""
        conf = edge_adjusted_confidence(0.80, 5.0, edge_threshold=8.0)
        assert conf == 0.80

    def test_at_threshold(self):
        """Exactly at threshold -> no penalty."""
        conf = edge_adjusted_confidence(0.80, 8.0, edge_threshold=8.0)
        assert conf == 0.80

    def test_penalty_above_threshold(self):
        """Edge above threshold should reduce confidence."""
        conf = edge_adjusted_confidence(0.80, 16.0, edge_threshold=8.0, max_edge_penalty=0.15)
        # excess = 8, penalty = 8/8 * 0.15 = 0.15 -> conf = 0.80 - 0.15 = 0.65
        assert abs(conf - 0.65) < 0.001

    def test_penalty_capped_at_max(self):
        """Penalty should not exceed max_edge_penalty."""
        conf = edge_adjusted_confidence(0.80, 50.0, edge_threshold=8.0, max_edge_penalty=0.15)
        # excess = 42, penalty = min(0.15, 42/8 * 0.15) = 0.15
        assert abs(conf - 0.65) < 0.001

    def test_minimum_floor(self):
        """Should not drop below 0.05."""
        conf = edge_adjusted_confidence(0.10, 50.0, edge_threshold=8.0, max_edge_penalty=0.15)
        assert conf == 0.05

    def test_negative_edge_no_penalty(self):
        """Negative edges should not apply penalty (abs used)."""
        conf = edge_adjusted_confidence(0.80, -5.0, edge_threshold=8.0)
        assert conf == 0.80


# ===================================================================
# confidence_adjusted_kelly
# ===================================================================

class TestConfidenceAdjustedKelly:
    """Tests for confidence_adjusted_kelly()."""

    def test_full_confidence(self):
        """With confidence=1.0, adjusted_prob == model_prob."""
        result = confidence_adjusted_kelly(0.60, 2.0, confidence=1.0, fraction=0.5)
        expected = fractional_kelly(0.60, 2.0, 0.5)
        assert abs(result - expected) < 0.0001

    def test_zero_confidence_fair_odds(self):
        """With confidence=0.0, adjusted_prob=0.5, so Kelly=0 for fair odds."""
        result = confidence_adjusted_kelly(0.60, 2.0, confidence=0.0, fraction=0.5)
        assert result == 0.0

    def test_half_confidence(self):
        """At confidence=0.5, prob is pulled halfway to 0.5."""
        result = confidence_adjusted_kelly(0.70, 2.0, confidence=0.5, fraction=0.5)
        # adjusted_prob = 0.5 * 0.70 + 0.5 * 0.50 = 0.60
        expected = fractional_kelly(0.60, 2.0, 0.5)
        assert abs(result - expected) < 0.0001

    def test_confidence_clamped_above_one(self):
        """Confidence > 1.0 should be clamped to 1.0."""
        result = confidence_adjusted_kelly(0.60, 2.0, confidence=1.5)
        expected = confidence_adjusted_kelly(0.60, 2.0, confidence=1.0)
        assert abs(result - expected) < 0.0001

    def test_confidence_clamped_below_zero(self):
        """Confidence < 0.0 should be clamped to 0.0."""
        result = confidence_adjusted_kelly(0.60, 2.0, confidence=-0.5)
        expected = confidence_adjusted_kelly(0.60, 2.0, confidence=0.0)
        assert abs(result - expected) < 0.0001


# ===================================================================
# goalie_matchup_adjustment
# ===================================================================

class TestGoalieMatchupAdjustment:
    """Tests for goalie_matchup_adjustment()."""

    def test_equal_goalies(self):
        adj = goalie_matchup_adjustment(0.910, 0.910)
        assert abs(adj) < 0.0001

    def test_home_better_goalie(self):
        # 0.920 - 0.900 = 0.02, * 1.5 * 100 = 3.0pp
        adj = goalie_matchup_adjustment(0.920, 0.900, impact_scaling=1.5)
        assert abs(adj - 3.0) < 0.01

    def test_away_better_goalie(self):
        adj = goalie_matchup_adjustment(0.900, 0.920, impact_scaling=1.5)
        assert abs(adj - (-3.0)) < 0.01

    def test_invalid_save_pct_returns_zero(self):
        assert goalie_matchup_adjustment(0.0, 0.910) == 0.0
        assert goalie_matchup_adjustment(0.910, 0.0) == 0.0
        assert goalie_matchup_adjustment(-0.1, 0.910) == 0.0


# ===================================================================
# Cross-function consistency checks
# ===================================================================

class TestCrossFunctionConsistency:
    """Tests verifying consistency between related functions."""

    def test_decimal_and_implied_are_inverse(self):
        """Decimal odds and implied probability should be consistent.

        implied_prob = 1 / decimal_odds (for a fair bet without vig).
        """
        for odds in [150, -150, 200, -200, 100, -100, -110]:
            dec = american_to_decimal(odds)
            imp = american_to_implied_probability(odds)
            # For fair (no-vig) odds: implied = 1/decimal
            assert abs(imp - 1.0 / dec) < 0.0001, (
                f"Odds {odds}: implied {imp} != 1/decimal {1.0/dec}"
            )

    def test_ev_and_kelly_agree_on_sign(self):
        """EV > 0 <=> Kelly > 0 for valid decimal odds."""
        cases = [
            (0.55, 1.91), (0.50, 2.00), (0.30, 2.00), (0.70, 1.50),
            (0.40, 3.00), (0.60, 1.80), (0.45, 2.10),
        ]
        for p, d in cases:
            ev = expected_value_per_dollar(p, d)
            kf = kelly_fraction(p, d)
            if ev > 0.0001:
                assert kf > 0, f"EV>0 but Kelly=0 for p={p}, d={d}"
            elif ev < -0.0001:
                assert kf == 0.0, f"EV<0 but Kelly>0 for p={p}, d={d}"

    def test_fractional_kelly_proportional(self):
        """fractional_kelly should always be fraction * kelly_fraction."""
        for frac in [0.1, 0.25, 0.5, 0.75, 1.0]:
            full = kelly_fraction(0.60, 2.0)
            partial = fractional_kelly(0.60, 2.0, frac)
            assert abs(partial - full * frac) < 0.0001


# ===================================================================
# Numerical stability
# ===================================================================

class TestNumericalStability:
    """Tests for numerical stability at extreme inputs."""

    def test_very_long_shot(self):
        """Very long odds (e.g., +99999) should not overflow."""
        dec = american_to_decimal(99999)
        imp = american_to_implied_probability(99999)
        assert dec > 1.0
        assert 0 < imp < 0.01

    def test_heavy_favorite(self):
        """Very short odds (e.g., -99999) should not overflow."""
        dec = american_to_decimal(-99999)
        imp = american_to_implied_probability(-99999)
        assert 1.0 < dec < 1.01
        assert 0.99 < imp < 1.0

    def test_logistic_extreme_strength_values(self):
        """Should handle extreme strength differences without math errors."""
        hp, ap = logistic_win_probability(1e10, -1e10, 0.0, 1.0)
        assert hp == 0.99
        assert abs(ap - 0.01) < 0.0001

    def test_decay_weight_no_overflow(self):
        """Decay with extremely large days_ago should return near-zero, not error."""
        w = exponential_decay_weight(1e10, 30.0)
        assert w == 0.0 or w >= 0.0  # Should not raise
