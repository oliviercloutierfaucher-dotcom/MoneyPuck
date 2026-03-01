from app.math_utils import (
    american_to_decimal,
    american_to_implied_probability,
    expected_value_per_dollar,
    kelly_fraction,
)


def test_american_conversions():
    assert round(american_to_decimal(150), 2) == 2.5
    assert round(american_to_decimal(-200), 2) == 1.5
    assert round(american_to_implied_probability(150), 3) == 0.4
    assert round(american_to_implied_probability(-200), 3) == 0.667


def test_ev_and_kelly():
    ev = expected_value_per_dollar(0.55, 2.1)
    assert ev > 0
    kelly = kelly_fraction(0.55, 2.1)
    assert kelly > 0
