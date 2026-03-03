from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from .agents import EdgeScoringAgent, MarketOddsAgent, MoneyPuckDataAgent, RiskAgent, TeamStrengthAgent
from .models import MarketSnapshot, TrackerConfig
from .nhl_api import fetch_goalie_stats


def _fetch_goalies_safe() -> list[dict]:
    """Best-effort goalie stats — returns empty list on failure."""
    try:
        return fetch_goalie_stats()
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: goalie fetch failed: {exc}", file=sys.stderr)
        return []


def build_market_snapshot(config: TrackerConfig) -> tuple[MarketSnapshot, list[dict[str, str]]]:
    """Fetch provider data once and construct reusable modeling inputs.

    Returns the snapshot **and** the raw MoneyPuck game rows so that
    downstream agents (e.g. situational factors) can use them.
    """
    market_agent = MarketOddsAgent()
    data_agent = MoneyPuckDataAgent()
    strength_agent = TeamStrengthAgent()

    with ThreadPoolExecutor(max_workers=3) as pool:
        odds_future = pool.submit(market_agent.run, config)
        moneypuck_future = pool.submit(data_agent.run, config)
        goalie_future = pool.submit(_fetch_goalies_safe)
        odds_events = odds_future.result()
        games_rows = moneypuck_future.result()
        goalie_stats = goalie_future.result()

    snapshot = MarketSnapshot(
        odds_events=odds_events,
        team_strength=strength_agent.run(games_rows, config, goalie_stats),
        goalie_stats=goalie_stats,
    )
    return snapshot, games_rows


def score_snapshot(
    snapshot: MarketSnapshot,
    config: TrackerConfig,
    games_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Score one config against an already-fetched market snapshot."""
    edge_agent = EdgeScoringAgent()
    risk_agent = RiskAgent()
    candidates = edge_agent.run(
        snapshot.odds_events, snapshot.team_strength, config, games_rows
    )
    return risk_agent.run(candidates, config)


def run_tracker(config: TrackerConfig) -> list[dict[str, object]]:
    """Run a full cycle with specialized agents.

    Organization model:
    - market-odds-agent, moneypuck-data-agent, and goalie-fetch run in parallel
    - team-strength-agent builds ratings (enriched with goalie data)
    - edge-scoring-agent prices edges (with situational + goalie adjustments)
    - risk-agent produces bankroll-aware stake sizes
    - (optional) persist predictions to SQLite
    """
    snapshot, games_rows = build_market_snapshot(config)
    recommendations = score_snapshot(snapshot, config, games_rows)

    # Phase 4: persist predictions when configured
    if config.persist and recommendations:
        _persist_recommendations(recommendations, config)

    return recommendations


def _persist_recommendations(
    recommendations: list[dict[str, object]],
    config: TrackerConfig,
    profile: str = "default",
) -> None:
    """Save recommendations to the tracker database."""
    from .database import TrackerDatabase

    with TrackerDatabase() as db:
        for rec in recommendations:
            db.save_prediction(rec, profile=profile)

        # Save run summary
        total_stake = sum(float(r["recommended_stake"]) for r in recommendations)
        edges = [r["candidate"].edge_probability_points for r in recommendations]
        evs = [r["candidate"].expected_value_per_dollar for r in recommendations]
        avg_edge = sum(edges) / len(edges) if edges else 0.0
        avg_ev = sum(evs) / len(evs) if evs else 0.0

        db.save_run(
            profile=profile,
            config_json=json.dumps({
                "season": config.season,
                "min_edge": config.min_edge,
                "min_ev": config.min_ev,
                "kelly_fraction": config.kelly_fraction,
                "half_life": config.half_life,
                "regression_k": config.regression_k,
                "home_advantage": config.home_advantage,
                "goalie_impact": config.goalie_impact,
            }),
            total_candidates=len(recommendations),
            total_stake=total_stake,
            avg_edge=avg_edge,
            avg_ev=avg_ev,
        )
