"""Phase 4: Tests for model quality validation metrics."""
from __future__ import annotations

import pytest

from app.validation import (
    brier_score,
    calibration_buckets,
    closing_line_value,
    roi_summary,
)


# ---------------------------------------------------------------------------
# Brier score
# ---------------------------------------------------------------------------


def test_brier_score_perfect():
    """Perfectly calibrated predictions should yield a Brier score of 0.0."""
    # Model says 1.0, outcome is 1 → error = 0; model says 0.0, outcome is 0 → error = 0
    predictions = [(1.0, 1), (1.0, 1), (0.0, 0), (0.0, 0)]
    assert brier_score(predictions) == 0.0


def test_brier_score_coin_flip():
    """Constant 0.5 probability predictions should give a Brier score near 0.25."""
    # With p=0.5, (0.5 - outcome)^2 = 0.25 for every outcome, regardless of label.
    predictions = [(0.5, outcome) for outcome in [1, 0, 1, 0, 1, 1, 0, 0]]
    score = brier_score(predictions)
    assert abs(score - 0.25) < 1e-9


def test_brier_score_single_correct():
    """A single perfectly correct prediction has score 0."""
    assert brier_score([(0.9, 1)]) == pytest.approx((0.9 - 1) ** 2, abs=1e-9)


def test_brier_score_empty_raises():
    """Empty input should raise ValueError."""
    with pytest.raises(ValueError):
        brier_score([])


# ---------------------------------------------------------------------------
# Closing Line Value
# ---------------------------------------------------------------------------


def test_clv_positive():
    """Betting +120 when line closes +110 should yield positive CLV.

    implied(+110) > implied(+120) so the close is harder to beat;
    we got a better price than the market settled at.
    """
    clv = closing_line_value(bet_odds=120, closing_odds=110)
    assert clv > 0.0


def test_clv_negative():
    """Betting +110 when line closes +120 should yield negative CLV.

    implied(+120) < implied(+110), so the line moved in our favour after we
    bet — the market thinks this side is *less* likely to win at close than
    when we bet.  We paid more implied probability than the market settled at,
    meaning we did NOT beat the closing line.

    close_implied(+120) ≈ 0.4545 < bet_implied(+110) ≈ 0.4762
    CLV = (0.4545 - 0.4762) * 100 ≈ -2.2 pp  →  negative.
    """
    clv = closing_line_value(bet_odds=110, closing_odds=120)
    assert clv < 0.0


def test_clv_same_odds_zero():
    """When bet odds equal closing odds the CLV should be zero."""
    clv = closing_line_value(bet_odds=-110, closing_odds=-110)
    assert abs(clv) < 1e-9


def test_clv_units_are_percentage_points():
    """CLV is in percentage points, not decimal fractions."""
    # implied(+100) = 0.5; implied(-110) ≈ 0.5238
    # CLV = (0.5238 - 0.5) * 100 ≈ 2.38 pp
    clv = closing_line_value(bet_odds=100, closing_odds=-110)
    assert 1.0 < clv < 5.0  # clearly in percentage-point territory


# ---------------------------------------------------------------------------
# Calibration buckets
# ---------------------------------------------------------------------------


def test_calibration_buckets_shape():
    """calibration_buckets returns at most n_buckets items; each has correct keys."""
    predictions = [(i / 20, i % 2) for i in range(20)]  # 20 pairs spanning [0, 0.95]
    result = calibration_buckets(predictions, n_buckets=10)

    assert isinstance(result, list)
    assert len(result) <= 10
    for bucket in result:
        assert "predicted" in bucket
        assert "actual" in bucket
        assert "count" in bucket
        assert bucket["count"] >= 1
        assert 0.0 <= bucket["predicted"] <= 1.0
        assert 0.0 <= bucket["actual"] <= 1.0


def test_calibration_buckets_count_sum():
    """Total count across all buckets must equal total number of predictions."""
    n = 30
    predictions = [(i / n, i % 2) for i in range(n)]
    result = calibration_buckets(predictions, n_buckets=5)
    assert sum(b["count"] for b in result) == n


def test_calibration_single_bucket():
    """All predictions in one bucket: one dict returned with correct actual rate."""
    predictions = [(0.1, 1), (0.1, 0), (0.1, 1)]  # all in bucket 0 with n_buckets=10
    result = calibration_buckets(predictions, n_buckets=10)
    assert len(result) == 1
    assert result[0]["count"] == 3
    assert abs(result[0]["actual"] - 2 / 3) < 1e-9


# ---------------------------------------------------------------------------
# ROI summary
# ---------------------------------------------------------------------------


def test_roi_summary_empty():
    """Empty settled list returns all-zero summary."""
    summary = roi_summary([])
    assert summary["n_bets"] == 0
    assert summary["total_staked"] == 0.0
    assert summary["roi_pct"] == 0.0
    assert summary["win_rate"] == 0.0


def test_roi_summary_all_wins():
    """Two winning bets at +100 (even money) → 100% ROI."""
    settled = [
        {"recommended_stake": 10.0, "profit_loss": 10.0, "outcome": "win"},
        {"recommended_stake": 10.0, "profit_loss": 10.0, "outcome": "win"},
    ]
    summary = roi_summary(settled)
    assert summary["n_bets"] == 2
    assert abs(summary["total_staked"] - 20.0) < 1e-6
    assert abs(summary["total_pnl"] - 20.0) < 1e-6
    assert abs(summary["roi_pct"] - 100.0) < 1e-4
    assert summary["win_rate"] == 1.0


def test_roi_summary_mixed():
    """One win ($10 profit) and one loss (-$10) → 0% ROI, 50% win rate."""
    settled = [
        {"recommended_stake": 10.0, "profit_loss": 10.0, "outcome": "win"},
        {"recommended_stake": 10.0, "profit_loss": -10.0, "outcome": "loss"},
    ]
    summary = roi_summary(settled)
    assert abs(summary["roi_pct"]) < 1e-6
    assert abs(summary["win_rate"] - 0.5) < 1e-6
    assert summary["n_bets"] == 2


def test_roi_summary_known_values():
    """Verify ROI formula: three bets, $100 total staked, $7 net profit → 7% ROI."""
    settled = [
        {"recommended_stake": 50.0, "profit_loss": 45.0, "outcome": "win"},
        {"recommended_stake": 30.0, "profit_loss": -30.0, "outcome": "loss"},
        {"recommended_stake": 20.0, "profit_loss": -8.0, "outcome": "loss"},
    ]
    summary = roi_summary(settled)
    assert abs(summary["total_staked"] - 100.0) < 1e-6
    assert abs(summary["total_pnl"] - 7.0) < 1e-6
    assert abs(summary["roi_pct"] - 7.0) < 1e-4
    assert abs(summary["win_rate"] - 1 / 3) < 1e-6
