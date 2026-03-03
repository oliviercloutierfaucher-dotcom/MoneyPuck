from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Any

from .logging_config import get_logger
from .models import TrackerConfig
from .presentation import to_serializable
from .service import build_market_snapshot, score_snapshot

log = get_logger("army")

ARMY_PROFILES: dict[str, dict[str, float]] = {
    "scout": {"min_edge": 1.0, "min_ev": 0.0, "max_fraction_per_bet": 0.02, "kelly_fraction": 0.3, "max_nightly_exposure": 0.10},
    "balanced": {"min_edge": 2.0, "min_ev": 0.02, "max_fraction_per_bet": 0.03, "kelly_fraction": 0.5, "max_nightly_exposure": 0.15},
    "sniper": {"min_edge": 3.5, "min_ev": 0.05, "max_fraction_per_bet": 0.025, "kelly_fraction": 0.5, "max_nightly_exposure": 0.12},
    "aggressive": {"min_edge": 2.5, "min_ev": 0.03, "max_fraction_per_bet": 0.05, "kelly_fraction": 0.7, "max_nightly_exposure": 0.20},
    "capital-preservation": {"min_edge": 4.0, "min_ev": 0.06, "max_fraction_per_bet": 0.015, "kelly_fraction": 0.25, "max_nightly_exposure": 0.08},
}


def _run_profile(
    profile_name: str,
    base_config: TrackerConfig,
    shared_snapshot: object,
    games_rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    tuning = ARMY_PROFILES[profile_name]
    profile_config = replace(
        base_config,
        min_edge=tuning["min_edge"],
        min_ev=tuning["min_ev"],
        max_fraction_per_bet=tuning["max_fraction_per_bet"],
        kelly_fraction=tuning.get("kelly_fraction", base_config.kelly_fraction),
        max_nightly_exposure=tuning.get("max_nightly_exposure", base_config.max_nightly_exposure),
    )
    recommendations = score_snapshot(shared_snapshot, profile_config, games_rows)
    serializable = to_serializable(recommendations)

    log.info("Profile '%s': %d opportunities found", profile_name, len(serializable))
    return {
        "profile": profile_name,
        "config": {
            "min_edge": profile_config.min_edge,
            "min_ev": profile_config.min_ev,
            "max_fraction_per_bet": profile_config.max_fraction_per_bet,
        },
        "count": len(serializable),
        "top_opportunities": serializable[:5],
    }


def run_agent_army(base_config: TrackerConfig, max_workers: int = 5) -> list[dict[str, Any]]:
    """Run all profile agents off one shared data snapshot.

    This avoids duplicate provider calls and keeps every profile compared on
    the exact same market data instant.
    """
    log.info("Starting army mode with %d profiles", len(ARMY_PROFILES))
    shared_snapshot, games_rows = build_market_snapshot(base_config)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_profile, name, base_config, shared_snapshot, games_rows): name
            for name in ARMY_PROFILES
        }
        for future in as_completed(futures):
            profile = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                log.error("Profile '%s' failed: %s", profile, exc)
                results.append({"profile": profile, "error": str(exc), "count": 0, "top_opportunities": []})

    log.info("Army mode complete: %d profiles executed", len(results))
    return sorted(results, key=lambda item: item.get("count", 0), reverse=True)
