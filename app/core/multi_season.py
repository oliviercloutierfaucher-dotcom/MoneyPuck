"""Multi-season data loading, walk-forward validation, and parameter stability.

Provides infrastructure for loading MoneyPuck data across multiple NHL seasons
(2015+), handling historical team code changes (ARI -> UTA, SEA expansion),
walk-forward validation with Elo carry-over, parameter stability analysis,
and overfit/drift/stable verdict determination.
"""

from __future__ import annotations

import statistics
from typing import Any

from app.core.backtester import (
    backtest_season,
    evaluate_predictions,
    grid_search,
    simulate_betting_roi,
)
from app.core.models import TrackerConfig
from app.data.data_sources import NHL_TEAMS, fetch_team_game_by_game
from app.logging_config import get_logger
from app.math.elo import EloTracker

log = get_logger("multi_season")


# ---------------------------------------------------------------------------
# Historical team code mapping
# ---------------------------------------------------------------------------

# Era boundaries for team code changes affecting 2015+ seasons:
# - Seattle Kraken (SEA) joined the NHL in the 2021-22 season (season=2021)
# - Arizona Coyotes (ARI) became Utah Hockey Club (UTA) in 2024-25 (season=2024)
# - Vegas Golden Knights (VGK) joined in 2017-18 (season=2017)
#   VGK is already in NHL_TEAMS; seasons before 2017 just won't have VGK data

HISTORICAL_TEAMS_BY_ERA: dict[str, dict[str, Any]] = {
    "sea_expansion": {
        "first_season": 2021,
        "team": "SEA",
        "note": "Seattle Kraken expansion team",
    },
    "ari_to_uta": {
        "last_season_as_ari": 2023,
        "old_code": "ARI",
        "new_code": "UTA",
        "note": "Arizona Coyotes relocated to Utah Hockey Club",
    },
    "vgk_expansion": {
        "first_season": 2017,
        "team": "VGK",
        "note": "Vegas Golden Knights expansion team",
    },
}


def get_teams_for_season(season: int) -> list[str]:
    """Return the correct list of NHL team codes for a given season.

    Handles historical changes:
    - Pre-2021: no SEA (Seattle Kraken hadn't joined yet)
    - Pre-2024: ARI instead of UTA (Arizona hadn't relocated yet)
    - Pre-2017: no VGK (Vegas hadn't joined yet)

    Parameters
    ----------
    season : int
        The season start year (e.g., 2024 for the 2024-25 season).

    Returns
    -------
    list[str]
        Sorted list of 3-letter team codes for that season.
    """
    teams = list(NHL_TEAMS)

    # Handle ARI <-> UTA
    if season < 2024:
        if "UTA" in teams:
            teams.remove("UTA")
        if "ARI" not in teams:
            teams.append("ARI")
    # For season >= 2024, UTA is already in NHL_TEAMS and ARI is not

    # Handle SEA expansion
    if season < 2021:
        if "SEA" in teams:
            teams.remove("SEA")

    # Handle VGK expansion
    if season < 2017:
        if "VGK" in teams:
            teams.remove("VGK")

    return sorted(teams)


def load_seasons(
    start_season: int = 2015,
    end_season: int = 2024,
) -> dict[int, list[dict[str, str]]]:
    """Load MoneyPuck game data for multiple seasons.

    For each season in the range [start_season, end_season], fetches per-team
    game-by-game data using the correct team codes for that era. Seasons that
    fail to load (404, network errors) are skipped gracefully.

    Parameters
    ----------
    start_season : int
        First season to load (inclusive).
    end_season : int
        Last season to load (inclusive).

    Returns
    -------
    dict[int, list[dict[str, str]]]
        Mapping of season year -> list of game rows.
    """
    seasons_data: dict[int, list[dict[str, str]]] = {}
    loaded: list[int] = []
    skipped: list[int] = []

    for season in range(start_season, end_season + 1):
        teams = get_teams_for_season(season)
        try:
            rows = fetch_team_game_by_game(season, teams=teams, fallback_to_bulk=False)
            if rows:
                seasons_data[season] = rows
                loaded.append(season)
                log.info("Season %d: loaded %d game rows", season, len(rows))
            else:
                skipped.append(season)
                log.warning("Season %d: no data returned, skipping", season)
        except Exception as exc:
            skipped.append(season)
            log.warning("Season %d: failed to load (%s), skipping", season, exc)

    log.info(
        "Loaded %d seasons: %s, skipped %d: %s",
        len(loaded), loaded, len(skipped), skipped,
    )
    return seasons_data


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

COVID_SEASON = 2020  # The 2020-21 season (56-game, hub cities)

# Reduced grid for per-season search (81 combos vs 1050 default)
REDUCED_PARAM_GRID = {
    "half_life": [21, 30, 45],
    "regression_k": [15, 20, 25],
    "home_advantage": [0.10, 0.14, 0.20],
    "logistic_k": [0.7, 0.9, 1.2],
}


def validate_multi_season(
    seasons: dict[int, list[dict]] | None = None,
    config: TrackerConfig | None = None,
    mode: str = "fixed",
    start_season: int = 2015,
    end_season: int = 2024,
) -> dict[str, Any]:
    """Run walk-forward validation across multiple seasons.

    Parameters
    ----------
    seasons : dict, optional
        Pre-loaded seasons data. If None, calls load_seasons().
    config : TrackerConfig, optional
        Model configuration. Uses defaults if None.
    mode : str
        "fixed" -- run each season with production params.
        "grid_search" -- find per-season optimal params via grid search.
    start_season, end_season : int
        Season range (used only if seasons is None).

    Returns
    -------
    dict with: season_results, overall_pass, mode, config_used,
    and (if grid_search) param_stability, verdict.
    """
    if seasons is None:
        seasons = load_seasons(start_season, end_season)

    if config is None:
        config = TrackerConfig(odds_api_key="")

    elo_tracker = EloTracker()
    season_results: list[dict[str, Any]] = []
    per_season_optimal: dict[int, dict[str, float]] = {}

    for i, season in enumerate(sorted(seasons.keys())):
        games = seasons[season]

        # Regress Elo at season boundary (not for first season)
        if i > 0:
            elo_tracker.regress_to_mean()

        # Run backtest with carried-over Elo
        predictions = backtest_season(games, config, elo_tracker=elo_tracker)

        # Evaluate
        metrics = evaluate_predictions(predictions)
        roi = simulate_betting_roi(predictions)

        result: dict[str, Any] = {
            "season": season,
            "brier_score": metrics["brier_score"],
            "accuracy": metrics["accuracy"],
            "roi_pct": roi["roi_pct"],
            "win_rate": roi["win_rate"],
            "n_predictions": metrics["n_predictions"],
            "is_covid": season == COVID_SEASON,
        }
        season_results.append(result)

        # Grid search mode: find per-season optimal params
        if mode == "grid_search":
            gs_results = grid_search(
                games, config, param_grid=REDUCED_PARAM_GRID,
            )
            if gs_results:
                best = gs_results[0]
                per_season_optimal[season] = best["params"]

    # Overall pass/fail: every season must have accuracy >= 0.55 AND roi > 0
    overall_pass = all(
        r["accuracy"] >= 0.55 and r["roi_pct"] > 0.0
        for r in season_results
    )

    output: dict[str, Any] = {
        "season_results": season_results,
        "overall_pass": overall_pass,
        "mode": mode,
        "config_used": {
            "half_life": getattr(config, "half_life", 30.0),
            "regression_k": getattr(config, "regression_k", 20),
            "home_advantage": getattr(config, "home_advantage", 0.14),
            "logistic_k": getattr(config, "logistic_k", 0.9),
        },
    }

    if mode == "grid_search" and per_season_optimal:
        stability = analyze_parameter_stability(per_season_optimal)
        verdict = determine_verdict(season_results, stability)
        output["param_stability"] = stability
        output["verdict"] = verdict

    return output


# ---------------------------------------------------------------------------
# Parameter stability analysis
# ---------------------------------------------------------------------------

def analyze_parameter_stability(
    per_season_optimal: dict[int, dict[str, float]],
) -> dict[str, dict[str, Any]]:
    """Compute drift metrics for each tunable parameter across seasons.

    Parameters
    ----------
    per_season_optimal : dict
        Mapping of season -> {param_name: optimal_value}.

    Returns
    -------
    dict mapping param_name -> {mean, stdev, min, max,
    coefficient_of_variation, values_by_season}.
    """
    if not per_season_optimal:
        return {}

    # Collect all param names from first entry
    param_names = list(next(iter(per_season_optimal.values())).keys())
    stability: dict[str, dict[str, Any]] = {}

    for param in param_names:
        values = [
            per_season_optimal[s][param]
            for s in sorted(per_season_optimal.keys())
        ]
        mean = statistics.mean(values)

        if len(values) >= 2:
            stdev = statistics.stdev(values)
        else:
            stdev = 0.0

        cv = stdev / mean if mean != 0 else 0.0

        stability[param] = {
            "mean": mean,
            "stdev": stdev,
            "min": min(values),
            "max": max(values),
            "coefficient_of_variation": cv,
            "values_by_season": {
                s: per_season_optimal[s][param]
                for s in sorted(per_season_optimal.keys())
            },
        }

    return stability


# ---------------------------------------------------------------------------
# Verdict determination
# ---------------------------------------------------------------------------

def determine_verdict(
    season_results: list[dict[str, Any]],
    param_stability: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Determine overall model verdict based on season results and drift.

    Returns one of:
    - "VERDICT: Parameters are STABLE across seasons"
    - "VERDICT: Model performs well but parameters show DRIFT ..."
    - "VERDICT: Parameters are OVERFIT ..."
    """
    # Check 1: all seasons pass the strict criteria
    all_pass = all(
        r["accuracy"] >= 0.55 and r["roi_pct"] > 0.0
        for r in season_results
    )

    # Check 2: parameter drift (any param CV > 0.3)
    high_drift = False
    if param_stability:
        high_drift = any(
            p.get("coefficient_of_variation", 0) > 0.3
            for p in param_stability.values()
        )

    if not all_pass:
        return (
            "VERDICT: Parameters are OVERFIT -- "
            "model fails on held-out seasons"
        )

    if high_drift:
        return (
            "VERDICT: Model performs well but parameters show DRIFT -- "
            "current params may be season-specific"
        )

    return "VERDICT: Parameters are STABLE across seasons"


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_multi_season_report(results: dict[str, Any]) -> str:
    """Format walk-forward validation results into a human-readable report.

    Parameters
    ----------
    results : dict
        Output from validate_multi_season().

    Returns
    -------
    str
        Formatted multi-line report string.
    """
    w = 76
    lines: list[str] = []

    lines.append("=" * w)
    lines.append("  MONEYPUCK EDGE -- MULTI-SEASON VALIDATION REPORT")
    lines.append("=" * w)

    # Mode
    mode = results.get("mode", "fixed")
    if mode == "fixed":
        lines.append("\n  Mode: Fixed Parameters")
    else:
        lines.append("\n  Mode: Per-Season Grid Search")

    # Config used
    cfg = results.get("config_used", {})
    lines.append(
        f"  Config: home_advantage={cfg.get('home_advantage', '?')}, "
        f"logistic_k={cfg.get('logistic_k', '?')}, "
        f"half_life={cfg.get('half_life', '?')}, "
        f"regression_k={cfg.get('regression_k', '?')}"
    )

    # Per-season table
    lines.append(f"\n  {'Season':<8} {'Games':>7} {'Win Rate':>10} "
                 f"{'Brier':>7} {'ROI':>8} {'Status':>8}  Notes")
    lines.append("  " + "-" * 68)

    season_results = results.get("season_results", [])
    for sr in season_results:
        season = sr["season"]
        n = sr.get("n_predictions", 0)
        win_rate = sr.get("accuracy", 0)
        brier = sr.get("brier_score", 0)
        roi = sr.get("roi_pct", 0)
        passes = win_rate >= 0.55 and roi > 0
        status = "PASS" if passes else "FAIL"
        notes = ""
        if sr.get("is_covid"):
            notes = "*COVID (56-game season)*"

        lines.append(
            f"  {season:<8} {n:>7} {win_rate:>9.1%} "
            f"{brier:>7.3f} {roi:>+7.1f}% {status:>8}  {notes}"
        )

    # Parameter stability table (grid_search mode only)
    stability = results.get("param_stability")
    if stability:
        lines.append(f"\n  PARAMETER STABILITY")
        lines.append(f"  {'Param':<18} {'Mean':>8} {'StdDev':>8} "
                     f"{'Min':>8} {'Max':>8} {'CV':>6}  Verdict")
        lines.append("  " + "-" * 68)
        for param, stats in stability.items():
            cv = stats.get("coefficient_of_variation", 0)
            p_verdict = "STABLE" if cv <= 0.3 else "DRIFT"
            lines.append(
                f"  {param:<18} {stats['mean']:>8.3f} {stats['stdev']:>8.3f} "
                f"{stats['min']:>8.3f} {stats['max']:>8.3f} "
                f"{cv:>5.2f}  {p_verdict}"
            )

    # Overall pass/fail banner
    overall = results.get("overall_pass", False)
    lines.append("")
    if overall:
        lines.append("  [PASS] All seasons meet minimum criteria "
                     "(>=55% win rate, positive ROI)")
    else:
        lines.append("  [FAIL] One or more seasons below minimum criteria")

    # Verdict line
    verdict = results.get("verdict")
    if verdict:
        lines.append(f"\n  {verdict}")

    lines.append("\n" + "=" * w)
    return "\n".join(lines)
