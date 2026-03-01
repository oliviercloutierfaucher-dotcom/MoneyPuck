from app.models import ValueCandidate
from app.presentation import render_html_preview, to_serializable


def test_to_serializable_and_html_preview():
    candidate = ValueCandidate(
        commence_time_utc="2026-01-01T00:00:00Z",
        home_team="MTL",
        away_team="TOR",
        side="MTL",
        sportsbook="Book",
        american_odds=120,
        decimal_odds=2.2,
        implied_probability=0.45,
        no_vig_probability=0.43,
        model_probability=0.55,
        confidence_score=8.4,
        edge_probability_points=10.0,
        expected_value_per_dollar=0.21,
        kelly_fraction=0.12,
    )

    recommendations = [{"candidate": candidate, "recommended_stake": 30.0, "stake_fraction": 0.03}]
    serialized = to_serializable(recommendations)
    assert serialized[0]["home_team"] == "MTL"
    assert serialized[0]["recommended_stake"] == 30.0
    assert serialized[0]["model_probability"] == 0.55
    assert serialized[0]["confidence_score"] == 8.4

    html = render_html_preview(recommendations)
    assert "MoneyPuck Edge Intelligence" in html
    assert "Quiver-style signal dashboard" in html
    assert '"away_team": "TOR"' in html
