from app.agents import EdgeScoringAgent, RiskAgent
from app.models import TeamMetrics, TrackerConfig


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
    config = TrackerConfig(odds_api_key="x", min_edge=0.1, min_ev=-1)

    candidates = EdgeScoringAgent().run(odds_events, strength, config)
    assert candidates
    assert hasattr(candidates[0], "confidence")

    sized = RiskAgent().run(candidates, config)
    assert sized[0]["recommended_stake"] >= 0
