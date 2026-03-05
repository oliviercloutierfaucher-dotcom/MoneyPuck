from datetime import datetime, timedelta

from app.core.agents import EdgeScoringAgent, RiskAgent
from app.core.models import MarketSnapshot, TeamMetrics, TrackerConfig
from app.core.service import check_data_freshness


def test_edge_pipeline_minimal_event():
    odds_events = [
        {
            "commence_time": "2026-01-01T00:00:00Z",
            "home_team": "MTL",
            "away_team": "TOR",
            "bookmakers": [
                {
                    "title": "Book",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "MTL", "price": 120},
                                {"name": "TOR", "price": -130},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    strength = {
        "MTL": TeamMetrics(home_strength=0.6, away_strength=0.4, games_played=40, composite=0.5),
        "TOR": TeamMetrics(home_strength=-0.3, away_strength=-0.4, games_played=40, composite=-0.3),
    }
    # max_edge=100 to avoid the safety cap (this test is for pipeline mechanics, not edge limits)
    config = TrackerConfig(odds_api_key="x", min_edge=0.1, min_ev=-1, max_edge=100.0)

    candidates = EdgeScoringAgent().run(odds_events, strength, config)
    assert candidates
    assert hasattr(candidates[0], "confidence")

    sized = RiskAgent().run(candidates, config)
    assert sized[0]["recommended_stake"] >= 0


# ---------------------------------------------------------------------------
# Max edge cap tests
# ---------------------------------------------------------------------------

def test_max_edge_rejects_large_edges():
    """Edges above max_edge should be silently rejected."""
    # Create a scenario where the model sees a huge edge (MTL massively favored
    # but book has them as underdog)
    odds_events = [
        {
            "commence_time": "2026-01-01T00:00:00Z",
            "home_team": "MTL",
            "away_team": "TOR",
            "bookmakers": [
                {
                    "title": "Book",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "MTL", "price": 250},   # implied ~28.6%
                                {"name": "TOR", "price": -300},  # implied ~75%
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    strength = {
        "MTL": TeamMetrics(home_strength=2.0, away_strength=1.5, games_played=40, composite=1.8),
        "TOR": TeamMetrics(home_strength=-1.0, away_strength=-1.5, games_played=40, composite=-1.2),
    }

    # With max_edge=10: the huge MTL edge (model ~90% vs implied ~28%) should be rejected
    config_capped = TrackerConfig(odds_api_key="x", min_edge=0.1, min_ev=-1, max_edge=10.0)
    candidates_capped = EdgeScoringAgent().run(odds_events, strength, config_capped)
    # Filter: only MTL-side candidates
    mtl_bets = [c for c in candidates_capped if c.side == "MTL"]
    assert len(mtl_bets) == 0, "MTL edge >10pp should be rejected by cap"

    # Without cap (max_edge=100): should find the edge
    config_uncapped = TrackerConfig(odds_api_key="x", min_edge=0.1, min_ev=-1, max_edge=100.0)
    candidates_uncapped = EdgeScoringAgent().run(odds_events, strength, config_uncapped)
    mtl_bets_uncapped = [c for c in candidates_uncapped if c.side == "MTL"]
    assert len(mtl_bets_uncapped) > 0, "MTL edge should pass with high cap"


def test_max_edge_allows_reasonable_edges():
    """Edges below max_edge should pass through normally."""
    odds_events = [
        {
            "commence_time": "2026-01-01T00:00:00Z",
            "home_team": "MTL",
            "away_team": "TOR",
            "bookmakers": [
                {
                    "title": "Book",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "MTL", "price": 120},
                                {"name": "TOR", "price": -130},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    strength = {
        "MTL": TeamMetrics(home_strength=0.6, away_strength=0.4, games_played=40, composite=0.5),
        "TOR": TeamMetrics(home_strength=-0.3, away_strength=-0.4, games_played=40, composite=-0.3),
    }
    config = TrackerConfig(odds_api_key="x", min_edge=0.1, min_ev=-1, max_edge=10.0)

    candidates = EdgeScoringAgent().run(odds_events, strength, config)
    # Reasonable edges should still pass
    for c in candidates:
        assert c.edge_probability_points <= 10.0


# ---------------------------------------------------------------------------
# Data staleness tests
# ---------------------------------------------------------------------------

def test_fresh_data_no_warnings():
    """Fresh data with live odds should produce no warnings."""
    snapshot = MarketSnapshot(
        odds_events=[{"test": True}],
        team_strength={"A": TeamMetrics()},
        fetched_at=datetime.now(),
        odds_source="live",
        strength_source="team_gbg",
        teams_fetched=30,
    )
    warnings = check_data_freshness(snapshot)
    assert len(warnings) == 0


def test_stale_data_warning():
    """Data older than 6 hours should trigger a critical warning."""
    old_time = datetime.now() - timedelta(hours=8)
    snapshot = MarketSnapshot(
        odds_events=[{"test": True}],
        team_strength={"A": TeamMetrics()},
        fetched_at=old_time,
        odds_source="live",
        strength_source="team_gbg",
        teams_fetched=30,
    )
    warnings = check_data_freshness(snapshot)
    assert any("CRITICAL" in w and "hours old" in w for w in warnings)


def test_empty_odds_warning():
    """Empty odds should trigger a critical warning."""
    snapshot = MarketSnapshot(
        odds_events=[],
        fetched_at=datetime.now(),
        odds_source="empty",
        strength_source="team_gbg",
        teams_fetched=30,
    )
    warnings = check_data_freshness(snapshot)
    assert any("No odds data" in w for w in warnings)


def test_bulk_csv_fallback_warning():
    """Falling back to bulk CSV should trigger a warning."""
    snapshot = MarketSnapshot(
        odds_events=[{"test": True}],
        fetched_at=datetime.now(),
        odds_source="live",
        strength_source="bulk_csv",
        teams_fetched=30,
    )
    warnings = check_data_freshness(snapshot)
    assert any("bulk CSV" in w for w in warnings)


def test_low_team_count_warning():
    """Having too few teams should trigger a warning."""
    snapshot = MarketSnapshot(
        odds_events=[{"test": True}],
        fetched_at=datetime.now(),
        odds_source="live",
        strength_source="team_gbg",
        teams_fetched=15,
    )
    warnings = check_data_freshness(snapshot)
    assert any("15 teams" in w for w in warnings)
