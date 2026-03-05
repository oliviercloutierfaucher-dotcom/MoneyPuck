from __future__ import annotations

import concurrent.futures
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.core.agents import EdgeScoringAgent, MarketOddsAgent, MoneyPuckDataAgent, RiskAgent, TeamStrengthAgent
from app.logging_config import get_logger
from app.core.models import MarketSnapshot, TrackerConfig
from app.data.nhl_api import fetch_goalie_stats

log = get_logger("service")

# Maximum age of data before we refuse to generate recommendations (seconds)
MAX_DATA_AGE_SECONDS = 6 * 3600  # 6 hours


def _fetch_goalies_safe() -> list[dict]:
    """Best-effort goalie stats -- returns empty list on failure."""
    try:
        return fetch_goalie_stats()
    except Exception as exc:  # noqa: BLE001
        log.warning("Goalie fetch failed (non-critical): %s", exc)
        return []


def build_market_snapshot(config: TrackerConfig) -> tuple[MarketSnapshot, list[dict[str, str]]]:
    """Fetch provider data once and construct reusable modeling inputs.

    Returns the snapshot **and** the raw MoneyPuck game rows so that
    downstream agents (e.g. situational factors) can use them.
    """
    log.info("Building market snapshot (region=%s, season=%d)", config.region, config.season)
    market_agent = MarketOddsAgent()
    data_agent = MoneyPuckDataAgent()
    strength_agent = TeamStrengthAgent()

    with ThreadPoolExecutor(max_workers=3) as pool:
        odds_future = pool.submit(market_agent.run, config)
        moneypuck_future = pool.submit(data_agent.run, config)
        goalie_future = pool.submit(_fetch_goalies_safe)

        try:
            odds_events = odds_future.result(timeout=45)
        except concurrent.futures.TimeoutError:
            log.error("Odds API timed out after 45s — returning empty odds")
            odds_events = []
        except Exception as exc:  # noqa: BLE001
            log.error("Odds API call failed: %s", exc)
            odds_events = []

        try:
            games_rows = moneypuck_future.result(timeout=45)
        except concurrent.futures.TimeoutError:
            log.error("MoneyPuck API timed out after 45s — returning empty games")
            games_rows = []
        except Exception as exc:  # noqa: BLE001
            log.error("MoneyPuck API call failed: %s", exc)
            games_rows = []

        try:
            goalie_stats = goalie_future.result(timeout=45)
        except concurrent.futures.TimeoutError:
            log.error("Goalie stats fetch timed out after 45s — returning empty goalies")
            goalie_stats = []
        except Exception as exc:  # noqa: BLE001
            log.error("Goalie stats fetch failed: %s", exc)
            goalie_stats = []

    if not odds_events:
        log.warning("No odds events received — recommendations will be empty")

    # Determine data sources for staleness tracking
    odds_source = "live" if odds_events else "empty"
    if not odds_events and not games_rows:
        strength_source = "empty"
    elif games_rows and games_rows[0].get("playerTeam"):
        strength_source = "team_gbg"
    elif games_rows:
        strength_source = "bulk_csv"
    else:
        strength_source = "empty"

    log.info(
        "Snapshot data: %d odds events, %d game rows, %d goalies (odds=%s, strength=%s)",
        len(odds_events), len(games_rows), len(goalie_stats),
        odds_source, strength_source,
    )

    team_strength = strength_agent.run(games_rows, config, goalie_stats)

    snapshot = MarketSnapshot(
        odds_events=odds_events,
        team_strength=team_strength,
        goalie_stats=goalie_stats,
        fetched_at=datetime.now(),
        odds_source=odds_source,
        strength_source=strength_source,
        teams_fetched=len(team_strength),
    )
    log.info("Team strength computed for %d teams", len(snapshot.team_strength))
    return snapshot, games_rows


def check_data_freshness(snapshot: MarketSnapshot) -> list[str]:
    """Return a list of warning/error strings if data is stale or degraded.

    Empty list means data is fresh and reliable.
    """
    warnings: list[str] = []

    if snapshot.odds_source == "empty":
        warnings.append("CRITICAL: No odds data — cannot generate reliable recommendations")
    if snapshot.odds_source == "timeout":
        warnings.append("WARNING: Odds API timed out — data may be stale")

    if snapshot.strength_source == "empty":
        warnings.append("CRITICAL: No team strength data — model has no signal")
    elif snapshot.strength_source == "bulk_csv":
        warnings.append("WARNING: Using bulk CSV fallback — data may be stale (team GBG preferred)")

    if snapshot.teams_fetched < 20:
        warnings.append(
            f"WARNING: Only {snapshot.teams_fetched} teams have strength data "
            f"(expected 30+) — missing teams will default to 50/50"
        )

    if snapshot.fetched_at:
        age = (datetime.now() - snapshot.fetched_at).total_seconds()
        if age > MAX_DATA_AGE_SECONDS:
            hours = age / 3600
            warnings.append(
                f"CRITICAL: Data is {hours:.1f} hours old (max {MAX_DATA_AGE_SECONDS / 3600:.0f}h). "
                f"Re-fetch before placing bets."
            )

    return warnings


def score_snapshot(
    snapshot: MarketSnapshot,
    config: TrackerConfig,
    games_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Score one config against an already-fetched market snapshot.

    Checks data freshness first. If critical data issues are detected,
    logs warnings. Callers should check snapshot.odds_source and
    snapshot.strength_source before acting on recommendations.
    """
    # Data freshness warnings
    freshness_warnings = check_data_freshness(snapshot)
    for w in freshness_warnings:
        if w.startswith("CRITICAL"):
            log.error(w)
        else:
            log.warning(w)

    # Block recommendations on critically bad data
    critical = [w for w in freshness_warnings if w.startswith("CRITICAL")]
    if critical:
        log.error(
            "Refusing to generate recommendations due to data quality issues: %s",
            "; ".join(critical),
        )
        return []

    edge_agent = EdgeScoringAgent()
    risk_agent = RiskAgent()
    candidates = edge_agent.run(
        snapshot.odds_events, snapshot.team_strength, config, games_rows
    )
    recommendations = risk_agent.run(candidates, config)
    log.info(
        "Scoring complete: %d candidates -> %d recommendations",
        len(candidates), len(recommendations),
    )
    return recommendations


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
    from app.data.database import TrackerDatabase

    try:
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
        log.info("Persisted %d predictions to database", len(recommendations))
    except Exception:
        log.exception("Failed to persist predictions")
