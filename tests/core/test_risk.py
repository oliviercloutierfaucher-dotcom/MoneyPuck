"""Phase 3: Smart risk management tests."""

from app.core.agents import LineShoppingAgent, RiskAgent
from app.math.math_utils import confidence_adjusted_kelly, fractional_kelly
from app.core.models import TrackerConfig, ValueCandidate


def test_fractional_kelly_half():
    full = fractional_kelly(0.55, 2.1, fraction=1.0)
    half = fractional_kelly(0.55, 2.1, fraction=0.5)
    assert abs(half - full * 0.5) < 0.0001


def test_fractional_kelly_quarter():
    full = fractional_kelly(0.55, 2.1, fraction=1.0)
    quarter = fractional_kelly(0.55, 2.1, fraction=0.25)
    assert abs(quarter - full * 0.25) < 0.0001


def test_confidence_adjusted_kelly_full_confidence():
    base = fractional_kelly(0.55, 2.1, fraction=0.5)
    adj = confidence_adjusted_kelly(0.55, 2.1, confidence=1.0, fraction=0.5)
    assert abs(adj - base) < 0.0001


def test_confidence_adjusted_kelly_half_confidence():
    # confidence=0.5 blends model_prob toward 0.5:
    # adjusted_prob = 0.5 * 0.55 + 0.5 * 0.5 = 0.525
    expected = fractional_kelly(0.525, 2.1, fraction=0.5)
    adj = confidence_adjusted_kelly(0.55, 2.1, confidence=0.5, fraction=0.5)
    assert abs(adj - expected) < 0.0001


def test_confidence_adjusted_kelly_zero_confidence():
    # confidence=0 means adjusted_prob = 0.5 (the no-edge prior)
    # With odds 2.1, Kelly at prob=0.5 is still slightly positive
    expected = fractional_kelly(0.5, 2.1, fraction=0.5)
    adj = confidence_adjusted_kelly(0.55, 2.1, confidence=0.0, fraction=0.5)
    assert abs(adj - expected) < 0.0001
    assert adj > 0.0  # blending toward 0.5 with favorable odds is still +EV


def _make_candidate(side, sportsbook, odds, commence="2026-01-01T00:00:00Z",
                    home="MTL", away="TOR", confidence=0.8):
    dec = 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)
    return ValueCandidate(
        commence_time_utc=commence,
        home_team=home,
        away_team=away,
        side=side,
        sportsbook=sportsbook,
        american_odds=odds,
        decimal_odds=dec,
        implied_probability=0.45,
        model_probability=0.55,
        edge_probability_points=10.0,
        expected_value_per_dollar=0.20,
        kelly_fraction=0.10,
        confidence=confidence,
    )


def test_line_shopping_keeps_best_odds():
    candidates = [
        _make_candidate("MTL", "BookA", 110),
        _make_candidate("MTL", "BookB", 120),  # best
        _make_candidate("MTL", "BookC", 105),
    ]
    best = LineShoppingAgent.best_lines(candidates)
    assert len(best) == 1
    assert best[0].sportsbook == "BookB"


def test_line_shopping_different_sides():
    candidates = [
        _make_candidate("MTL", "BookA", 120),
        _make_candidate("TOR", "BookA", -110),
    ]
    best = LineShoppingAgent.best_lines(candidates)
    assert len(best) == 2  # different sides, both kept


def test_risk_agent_nightly_exposure_cap():
    # Create 10 candidates for same night with high kelly
    candidates = [
        _make_candidate("MTL", f"Book{i}", 120, confidence=1.0)
        for i in range(10)
    ]
    config = TrackerConfig(
        odds_api_key="x",
        bankroll=1000.0,
        max_fraction_per_bet=0.05,
        max_nightly_exposure=0.15,
        kelly_fraction=1.0,
        min_edge=0.0,
        min_ev=-1.0,
    )
    recs = RiskAgent().run(candidates, config)
    total_stake = sum(r["recommended_stake"] for r in recs)
    # Total should not exceed 15% of $1000 = $150
    assert total_stake <= 150.01


def test_risk_agent_confidence_reduces_stake():
    high_conf = [_make_candidate("MTL", "BookA", 120, confidence=1.0)]
    low_conf = [_make_candidate("MTL", "BookA", 120, confidence=0.3)]
    config = TrackerConfig(
        odds_api_key="x", bankroll=1000.0, min_edge=0.0, min_ev=-1.0,
        max_fraction_per_bet=0.15,  # raise cap so confidence difference is visible
    )
    rec_high = RiskAgent().run(high_conf, config)
    rec_low = RiskAgent().run(low_conf, config)
    assert rec_high[0]["recommended_stake"] > rec_low[0]["recommended_stake"]
