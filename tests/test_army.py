from app.army import ARMY_PROFILES, run_agent_army
from app.models import TrackerConfig, ValueCandidate


def test_army_runs_profiles(monkeypatch):
    def fake_run_tracker(_config):
        candidate = ValueCandidate(
            commence_time_utc="2026-01-01T00:00:00Z",
            home_team="MTL",
            away_team="TOR",
            side="MTL",
            sportsbook="Book",
            american_odds=110,
            decimal_odds=2.1,
            implied_probability=0.476,
            model_probability=0.54,
            edge_probability_points=6.4,
            expected_value_per_dollar=0.13,
            kelly_fraction=0.1,
        )
        return [{"candidate": candidate, "recommended_stake": 25.0, "stake_fraction": 0.025}]

    monkeypatch.setattr("app.army.run_tracker", fake_run_tracker)

    cfg = TrackerConfig(odds_api_key="x")
    results = run_agent_army(cfg)

    assert len(results) == len(ARMY_PROFILES)
    assert all("profile" in row for row in results)
    assert all("top_opportunities" in row for row in results)
