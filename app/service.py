from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .agents import EdgeScoringAgent, MarketOddsAgent, MoneyPuckDataAgent, RiskAgent, TeamStrengthAgent
from .models import TrackerConfig


def run_tracker(config: TrackerConfig) -> list[dict[str, object]]:
    """Run a full cycle with specialized agents.

    Organization model:
    - market-odds-agent and moneypuck-data-agent run in parallel
    - team-strength-agent builds ratings
    - edge-scoring-agent prices edges
    - risk-agent produces bankroll-aware stake sizes
    """
    market_agent = MarketOddsAgent()
    data_agent = MoneyPuckDataAgent()
    strength_agent = TeamStrengthAgent()
    edge_agent = EdgeScoringAgent()
    risk_agent = RiskAgent()

    with ThreadPoolExecutor(max_workers=2) as pool:
        odds_future = pool.submit(market_agent.run, config)
        moneypuck_future = pool.submit(data_agent.run, config)
        odds_events = odds_future.result()
        games_rows = moneypuck_future.result()

    team_strength = strength_agent.run(games_rows)
    candidates = edge_agent.run(odds_events, team_strength, config)
    return risk_agent.run(candidates, config)
