"""Tests for app.math.hedge module."""

from __future__ import annotations

import pytest

from app.math.hedge import calculate_cashout_value, calculate_hedge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EPSILON = 0.02  # dollar tolerance for floating-point comparisons


def approx(val: float, tol: float = EPSILON) -> float:
    """Return a pytest.approx with absolute tolerance."""
    return pytest.approx(val, abs=tol)


# ---------------------------------------------------------------------------
# calculate_hedge — lock_profit mode
# ---------------------------------------------------------------------------

class TestLockProfit:
    def test_equal_profit_on_both_outcomes(self):
        """The defining property of lock_profit: both outcomes yield equal P&L."""
        result = calculate_hedge(
            original_odds=2.50,
            original_stake=100.0,
            hedge_odds=2.10,
            mode="lock_profit",
        )
        assert result["profit_if_original_wins"] == approx(result["profit_if_hedge_wins"])

    def test_guaranteed_profit_is_minimum(self):
        """guaranteed_profit equals the smaller of the two profit figures."""
        result = calculate_hedge(2.50, 100.0, 2.10)
        expected = min(
            result["profit_if_original_wins"], result["profit_if_hedge_wins"]
        )
        assert result["guaranteed_profit"] == approx(expected)

    def test_roi_calculation(self):
        """ROI = guaranteed_profit / total_outlay * 100."""
        result = calculate_hedge(2.50, 100.0, 2.10)
        total_outlay = 100.0 + result["hedge_stake"]
        expected_roi = result["guaranteed_profit"] / total_outlay * 100
        assert result["roi_pct"] == approx(expected_roi)

    def test_even_odds_hedge(self):
        """Even-money original (2.0) hedged at even money → hedge_stake == original_stake."""
        result = calculate_hedge(2.0, 100.0, 2.0)
        assert result["hedge_stake"] == approx(100.0)
        assert result["guaranteed_profit"] == approx(0.0, tol=0.05)

    def test_heavy_favourite_hedge(self):
        """Short-priced original (1.20) hedged at long odds (5.00)."""
        result = calculate_hedge(
            original_odds=1.20,
            original_stake=500.0,
            hedge_odds=5.00,
        )
        # Original payout = 1.20 * 500 = 600
        # Hedge stake = 600 / 5.00 = 120
        assert result["hedge_stake"] == approx(120.0)
        assert result["profit_if_original_wins"] == approx(result["profit_if_hedge_wins"])

    def test_heavy_underdog_original(self):
        """Long-odds original (6.00) hedged at short odds (1.25)."""
        result = calculate_hedge(
            original_odds=6.00,
            original_stake=50.0,
            hedge_odds=1.25,
        )
        # Original payout = 300; hedge_stake = 300 / 1.25 = 240
        assert result["hedge_stake"] == approx(240.0)
        assert result["profit_if_original_wins"] == approx(result["profit_if_hedge_wins"])

    def test_true_arb_yields_positive_guaranteed_profit(self):
        """When the market is an arb (combined margin < 1), guaranteed_profit > 0."""
        # Arb: 1/2.20 + 1/2.20 ≈ 0.909 < 1
        result = calculate_hedge(2.20, 100.0, 2.20)
        assert result["guaranteed_profit"] > 0

    def test_positive_roi_on_arb(self):
        """An arbitrage situation should produce positive ROI."""
        result = calculate_hedge(2.20, 100.0, 2.20)
        assert result["roi_pct"] > 0


# ---------------------------------------------------------------------------
# calculate_hedge — minimize_loss mode
# ---------------------------------------------------------------------------

class TestMinimiseLoss:
    def test_minimize_loss_uses_lock_profit_when_arb_exists(self):
        """When a guaranteed profit is available, minimize_loss == lock_profit."""
        r_lock = calculate_hedge(2.20, 100.0, 2.20, mode="lock_profit")
        r_min = calculate_hedge(2.20, 100.0, 2.20, mode="minimize_loss")
        assert r_lock["hedge_stake"] == approx(r_min["hedge_stake"])

    def test_minimize_loss_on_negative_ev_hedge(self):
        """In a high-vig market, minimize_loss still reduces worst-case loss."""
        # Combined margin > 1 here: 1/1.5 + 1/1.5 ≈ 1.33 (high vig)
        result = calculate_hedge(1.50, 100.0, 1.50, mode="minimize_loss")
        # Both profit figures should be equal (equal worst-case loss)
        assert result["profit_if_original_wins"] == approx(
            result["profit_if_hedge_wins"]
        )

    def test_invalid_mode_raises(self):
        """An unknown mode string should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            calculate_hedge(2.50, 100.0, 2.10, mode="bad_mode")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_odds_below_1_raises(self):
        """Decimal odds <= 1.0 are invalid."""
        with pytest.raises(ValueError):
            calculate_hedge(0.9, 100.0, 2.0)

    def test_hedge_odds_below_1_raises(self):
        with pytest.raises(ValueError):
            calculate_hedge(2.0, 100.0, 1.0)

    def test_zero_stake_raises(self):
        with pytest.raises(ValueError):
            calculate_hedge(2.0, 0.0, 2.0)

    def test_negative_stake_raises(self):
        with pytest.raises(ValueError):
            calculate_hedge(2.0, -50.0, 2.0)


# ---------------------------------------------------------------------------
# calculate_cashout_value
# ---------------------------------------------------------------------------

class TestCashoutValue:
    def test_fair_value_at_original_odds(self):
        """If current odds equal original odds, fair cashout = original stake."""
        result = calculate_cashout_value(2.50, 100.0, 2.50)
        # current_implied_prob = 1/2.50 = 0.40; fair_value = 0.40 * 250 = 100
        assert result["fair_value"] == approx(100.0)

    def test_profit_if_cashout_at_original_odds(self):
        """At original odds, cashout profit should be ~0 (break-even)."""
        result = calculate_cashout_value(2.50, 100.0, 2.50)
        assert result["profit_if_cashout"] == approx(0.0)

    def test_fair_value_shorter_odds_means_profit(self):
        """If current odds are shorter (selection has moved in your favour), cashout > stake."""
        # Original: 3.00, current: 1.80 (moved heavily in favour)
        result = calculate_cashout_value(3.00, 100.0, 1.80)
        # implied_prob at 1.80 = 0.555...; payout = 300; fair_value ≈ 0.555 * 300 = 166.67
        assert result["fair_value"] > 100.0
        assert result["profit_if_cashout"] > 0.0

    def test_fair_value_longer_odds_means_loss(self):
        """If current odds have drifted out, fair cashout is below stake."""
        # Original: 2.00, current: 4.00 (selection has drifted badly)
        result = calculate_cashout_value(2.00, 100.0, 4.00)
        # implied_prob = 0.25; payout = 200; fair_value = 0.25 * 200 = 50
        assert result["fair_value"] == approx(50.0)
        assert result["profit_if_cashout"] == approx(-50.0)

    def test_ev_if_hold_positive_when_odds_shortened(self):
        """EV of holding should be positive when we are currently the favourite."""
        result = calculate_cashout_value(3.00, 100.0, 1.50)
        assert result["ev_if_hold"] > 0.0

    def test_ev_if_hold_negative_when_odds_drifted(self):
        """EV of holding should be negative when odds have drifted against us."""
        result = calculate_cashout_value(2.00, 100.0, 5.00)
        assert result["ev_if_hold"] < 0.0

    def test_cashout_invalid_odds_raises(self):
        with pytest.raises(ValueError):
            calculate_cashout_value(1.0, 100.0, 2.0)

    def test_cashout_zero_stake_raises(self):
        with pytest.raises(ValueError):
            calculate_cashout_value(2.0, 0.0, 2.0)
