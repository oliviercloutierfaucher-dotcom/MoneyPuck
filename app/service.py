from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .agents import EdgeScoringAgent, MarketOddsAgent, MoneyPuckDataAgent, RiskAgent, TeamStrengthAgent
from .models import MarketSnapshot, TrackerConfig


def build_market_snapshot(config: TrackerConfig) -> MarketSnapshot:
    """Fetch provider data once and construct reusable modeling inputs."""
    market_agent = MarketOddsAgent()
    data_agent = MoneyPuckDataAgent()
    strength_agent = TeamStrengthAgent()

    with ThreadPoolExecutor(max_workers=2) as pool:
        odds_future = pool.submit(market_agent.run, config)
        moneypuck_future = pool.submit(data_agent.run, config)
        odds_events = odds_future.result()
        games_rows = moneypuck_future.result()

    return MarketSnapshot(
        odds_events=odds_events,
        team_strength=strength_agent.run(games_rows),
    )


def score_snapshot(snapshot: MarketSnapshot, config: TrackerConfig) -> list[dict[str, object]]:
    """Score one config against an already-fetched market snapshot."""
    edge_agent = EdgeScoringAgent()
    risk_agent = RiskAgent()
    candidates = edge_agent.run(snapshot.odds_events, snapshot.team_strength, config)
    return risk_agent.run(candidates, config)


def run_tracker(config: TrackerConfig) -> list[dict[str, object]]:
    """Run a full cycle with specialized agents.

    Organization model:
    - market-odds-agent and moneypuck-data-agent run in parallel
    - team-strength-agent builds ratings
    - edge-scoring-agent prices edges
    - risk-agent produces bankroll-aware stake sizes
    """
    snapshot = build_market_snapshot(config)
    return score_snapshot(snapshot, config)
