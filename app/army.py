from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Any

from .models import TrackerConfig
from .presentation import to_serializable
from .service import run_tracker


ARMY_PROFILES: dict[str, dict[str, float]] = {
    "scout": {"min_edge": 1.0, "min_ev": 0.0, "max_fraction_per_bet": 0.02},
    "balanced": {"min_edge": 2.0, "min_ev": 0.02, "max_fraction_per_bet": 0.03},
    "sniper": {"min_edge": 3.5, "min_ev": 0.05, "max_fraction_per_bet": 0.025},
    "aggressive": {"min_edge": 2.5, "min_ev": 0.03, "max_fraction_per_bet": 0.05},
    "capital-preservation": {"min_edge": 4.0, "min_ev": 0.06, "max_fraction_per_bet": 0.015},
}


def _run_profile(profile_name: str, base_config: TrackerConfig) -> dict[str, Any]:
    tuning = ARMY_PROFILES[profile_name]
    profile_config = replace(
        base_config,
        min_edge=tuning["min_edge"],
        min_ev=tuning["min_ev"],
        max_fraction_per_bet=tuning["max_fraction_per_bet"],
    )
    recommendations = run_tracker(profile_config)
    serializable = to_serializable(recommendations)

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
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_profile, name, base_config): name for name in ARMY_PROFILES}
        for future in as_completed(futures):
            profile = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"profile": profile, "error": str(exc), "count": 0, "top_opportunities": []})

    return sorted(results, key=lambda item: item.get("count", 0), reverse=True)
