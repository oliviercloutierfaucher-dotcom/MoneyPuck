from __future__ import annotations

import concurrent.futures
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.core.agents import EdgeScoringAgent, MarketOddsAgent, MoneyPuckDataAgent, RiskAgent, TeamStrengthAgent
from app.logging_config import get_logger
from app.core.models import MarketSnapshot, TeamMetrics, TrackerConfig
from app.data.data_sources import fetch_polymarket_odds
from app.data.nhl_api import fetch_goalie_stats
from app.math.elo import build_elo_ratings

log = get_logger("service")

# Maximum age of data before we refuse to generate recommendations (seconds)
MAX_DATA_AGE_SECONDS = 6 * 3600  # 6 hours

# Circuit breaker: stop betting if recent model performance is poor
CIRCUIT_BREAKER_WINDOW = 50    # number of recent settled predictions to check
CIRCUIT_BREAKER_BRIER = 0.26   # Brier score threshold (0.25 = coin flip)


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

    with ThreadPoolExecutor(max_workers=4) as pool:
        odds_future = pool.submit(market_agent.run, config)
        moneypuck_future = pool.submit(data_agent.run, config)
        goalie_future = pool.submit(_fetch_goalies_safe)
        polymarket_future = pool.submit(fetch_polymarket_odds)

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

    # Merge Polymarket odds (best-effort — never blocks on failure)
    try:
        poly_events = polymarket_future.result(timeout=15)
    except Exception as exc:  # noqa: BLE001
        log.warning("Polymarket fetch failed: %s", exc)
        poly_events = []

    if poly_events:
        # Merge Polymarket as an additional bookmaker on matching events,
        # or add as new events if no Odds API match exists.
        existing_keys = {
            (e.get("home_team"), e.get("away_team")): e
            for e in odds_events
        }
        for pe in poly_events:
            key = (pe.get("home_team"), pe.get("away_team"))
            if key in existing_keys:
                # Add Polymarket as another bookmaker on the existing event
                existing_keys[key]["bookmakers"].extend(pe["bookmakers"])
            else:
                # New event only on Polymarket
                odds_events.append(pe)
        log.info(
            "Merged %d Polymarket events (%d total odds events)",
            len(poly_events), len(odds_events),
        )

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


def check_circuit_breaker() -> tuple[bool, str]:
    """Check if the model should stop betting based on recent performance.

    Examines the last CIRCUIT_BREAKER_WINDOW settled predictions. If the
    Brier score exceeds CIRCUIT_BREAKER_BRIER, the circuit breaker trips.

    Returns (tripped: bool, message: str).
    """
    try:
        from app.data.database import TrackerDatabase
        from app.math.validation import brier_score

        with TrackerDatabase() as db:
            settled = db.get_predictions()
            settled = [s for s in settled if s.get("outcome") is not None]

        if len(settled) < CIRCUIT_BREAKER_WINDOW:
            return False, f"Not enough settled predictions ({len(settled)}/{CIRCUIT_BREAKER_WINDOW})"

        # Take the most recent N predictions
        recent = settled[:CIRCUIT_BREAKER_WINDOW]
        pairs = []
        for s in recent:
            prob = s.get("model_probability")
            if prob is None:
                continue
            binary = 1 if s["outcome"] == "win" else 0
            pairs.append((float(prob), binary))

        if len(pairs) < CIRCUIT_BREAKER_WINDOW // 2:
            return False, f"Not enough predictions with probabilities ({len(pairs)})"

        score = brier_score(pairs)
        if score > CIRCUIT_BREAKER_BRIER:
            return True, (
                f"CIRCUIT BREAKER TRIPPED: Brier score {score:.4f} > {CIRCUIT_BREAKER_BRIER} "
                f"over last {len(pairs)} predictions. Model is performing worse than "
                f"a coin flip. Stop betting and investigate."
            )
        return False, f"Model healthy: Brier {score:.4f} over last {len(pairs)} predictions"

    except Exception as exc:  # noqa: BLE001
        log.error("Circuit breaker check failed — treating as healthy (fail-open): %s", exc)
        return False, f"Check failed: {exc}"


# Injury/roster overrides file: ~/.moneypuck/overrides.json
OVERRIDES_PATH = os.path.normpath(
    os.path.join(os.path.expanduser("~"), ".moneypuck", "overrides.json")
)


def load_overrides() -> dict[str, dict]:
    """Load team overrides from ~/.moneypuck/overrides.json.

    Expected format:
    {
        "TOR": {
            "strength_penalty": -0.3,
            "reason": "Matthews out (upper body)",
            "expires": "2026-03-15"
        },
        "EDM": {
            "exclude": true,
            "reason": "McDavid day-to-day, uncertain"
        }
    }

    Keys:
    - strength_penalty (float): Added to composite/home/away strength.
      Negative = team is weaker. Typical range: -0.1 to -0.5.
    - exclude (bool): If true, skip all bets involving this team.
    - reason (str): Human-readable note.
    - expires (str): ISO date after which the override is ignored.
    """
    try:
        with open(OVERRIDES_PATH) as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    today = datetime.now().strftime("%Y-%m-%d")
    active: dict[str, dict] = {}
    for team, override in raw.items():
        expires = override.get("expires", "")
        if expires and expires < today:
            log.info("Override for %s expired on %s — skipping", team, expires)
            continue
        active[team] = override

    if active:
        log.info("Active overrides: %s", ", ".join(f"{t} ({v.get('reason', '?')})" for t, v in active.items()))
    return active


def apply_overrides(
    team_strength: dict[str, TeamMetrics],
    overrides: dict[str, dict],
) -> dict[str, TeamMetrics]:
    """Apply injury/roster overrides to team strength ratings.

    Returns a new dict (does not mutate the original).
    """
    if not overrides:
        return team_strength

    from dataclasses import asdict
    result = dict(team_strength)
    for team, override in overrides.items():
        if team not in result:
            continue
        penalty = override.get("strength_penalty", 0.0)
        if penalty == 0.0:
            continue
        old = result[team]
        old_dict = asdict(old)
        old_dict["composite"] = old.composite + penalty
        old_dict["home_strength"] = old.home_strength + penalty
        old_dict["away_strength"] = old.away_strength + penalty
        result[team] = TeamMetrics(**old_dict)
        log.info(
            "Applied override to %s: strength %+.2f (%s)",
            team, penalty, override.get("reason", "no reason"),
        )
    return result


def get_excluded_teams(overrides: dict[str, dict]) -> set[str]:
    """Return set of teams that should be excluded from betting."""
    return {team for team, o in overrides.items() if o.get("exclude", False)}


def check_data_freshness(snapshot: MarketSnapshot) -> list[str]:
    """Return a list of warning/error strings if data is stale or degraded.

    Empty list means data is fresh and reliable.
    """
    warnings: list[str] = []

    if snapshot.odds_source == "empty":
        warnings.append("CRITICAL: No odds data — cannot generate reliable recommendations")

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
    # Circuit breaker: check recent model performance
    tripped, cb_msg = check_circuit_breaker()
    if tripped:
        log.error(cb_msg)
        return []

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

    # Load and apply injury/roster overrides
    overrides = load_overrides()
    team_strength = apply_overrides(snapshot.team_strength, overrides)
    excluded = get_excluded_teams(overrides)

    # Filter out events involving excluded teams
    odds_events = snapshot.odds_events
    if excluded:
        odds_events = [
            e for e in odds_events
            if e.get("home_team") not in excluded and e.get("away_team") not in excluded
        ]
        if len(odds_events) < len(snapshot.odds_events):
            log.info(
                "Excluded %d events involving teams: %s",
                len(snapshot.odds_events) - len(odds_events),
                ", ".join(sorted(excluded)),
            )

    # Build Elo ratings from historical game data for ensemble
    elo_tracker = None
    if games_rows:
        try:
            elo_tracker = build_elo_ratings(games_rows)
            log.info("Elo ratings built for %d teams", len(elo_tracker.ratings))
        except Exception:
            log.warning("Elo rating build failed — continuing without Elo ensemble")

    edge_agent = EdgeScoringAgent()
    risk_agent = RiskAgent()
    candidates = edge_agent.run(odds_events, team_strength, config, games_rows, elo_tracker)
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


def settle_outstanding() -> dict[str, object]:
    """Auto-settle unsettled predictions by fetching NHL game results.

    Matches unsettled predictions in the database to completed NHL games
    by date, home_team, and away_team.  Computes P&L based on the side
    bet and the final score.

    Returns a summary dict with settled count, total P&L, and any errors.
    """
    from app.data.database import TrackerDatabase
    from app.data.nhl_api import fetch_schedule, fetch_scores_for_date

    settled_count = 0
    total_pnl = 0.0
    errors: list[str] = []

    with TrackerDatabase() as db:
        unsettled = db.get_unsettled()
        if not unsettled:
            log.info("No unsettled predictions to process")
            return {"settled": 0, "total_pnl": 0.0, "errors": []}

        # Group unsettled by date to minimize API calls
        by_date: dict[str, list[dict]] = {}
        for pred in unsettled:
            commence = pred.get("commence_time", "")
            game_date = commence[:10] if commence else ""
            if game_date:
                by_date.setdefault(game_date, []).append(pred)

        # Fetch scores and schedule for each date
        scores_cache: dict[str, list[dict]] = {}
        schedule_cache: dict[str, list[dict]] = {}
        for game_date in by_date:
            try:
                scores_cache[game_date] = fetch_scores_for_date(game_date)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to fetch scores for %s: %s", game_date, exc)
                errors.append(f"Score fetch failed for {game_date}: {exc}")
            try:
                schedule_cache[game_date] = fetch_schedule(game_date)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to fetch schedule for %s: %s", game_date, exc)

        # Match and settle — wrap in a single transaction for atomicity
        db._conn.execute("BEGIN")
        try:
            for game_date, preds in by_date.items():
                scores = scores_cache.get(game_date, [])
                schedule = schedule_cache.get(game_date, [])

                # Build lookups
                score_lookup: dict[tuple[str, str], dict] = {}
                for score in scores:
                    key = (score["home_team"], score["away_team"])
                    score_lookup[key] = score

                # Detect postponed games from schedule
                ppd_games: set[tuple[str, str]] = set()
                for game in schedule:
                    if game.get("game_state") == "PPD":
                        ppd_games.add((game["home_team"], game["away_team"]))

                for pred in preds:
                    home = pred["home_team"]
                    away = pred["away_team"]

                    # Check for postponement first
                    if (home, away) in ppd_games:
                        db.settle(
                            prediction_id=pred["id"],
                            outcome="void",
                            closing_odds=None,
                            profit_loss=0.0,
                            auto_commit=False,
                        )
                        settled_count += 1
                        log.info("Voided #%d: %s @ %s — game postponed", pred["id"], away, home)
                        continue

                    score = score_lookup.get((home, away))
                    if not score:
                        continue

                    # Determine outcome
                    side = pred["side"]
                    home_score = score["home_score"]
                    away_score = score["away_score"]
                    winning_team = home if home_score > away_score else away

                    if home_score == away_score:
                        outcome = "push"
                        pnl = 0.0
                    elif side == winning_team:
                        outcome = "win"
                        decimal_odds = float(pred["decimal_odds"])
                        stake = float(pred["recommended_stake"])
                        pnl = round(stake * (decimal_odds - 1), 2)
                    else:
                        outcome = "loss"
                        pnl = -float(pred["recommended_stake"])

                    db.settle(
                        prediction_id=pred["id"],
                        outcome=outcome,
                        closing_odds=None,
                        profit_loss=pnl,
                        auto_commit=False,
                    )
                    settled_count += 1
                    total_pnl += pnl
                    log.info(
                        "Settled #%d: %s %s @ %s → %s (P&L: %+.2f)",
                        pred["id"], side, away, home, outcome, pnl,
                    )

            db._conn.commit()
        except Exception as exc:  # noqa: BLE001
            db._conn.rollback()
            log.error("Settlement transaction failed, rolled back: %s", exc)
            errors.append(f"Transaction failed: {exc}")

    return {
        "settled": settled_count,
        "total_pnl": round(total_pnl, 2),
        "errors": errors,
    }


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
