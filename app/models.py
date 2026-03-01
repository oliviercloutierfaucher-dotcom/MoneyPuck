from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValueCandidate:
    commence_time_utc: str
    home_team: str
    away_team: str
    side: str
    sportsbook: str
    american_odds: int
    decimal_odds: float
    implied_probability: float
    model_probability: float
    edge_probability_points: float
    expected_value_per_dollar: float
    kelly_fraction: float


@dataclass(frozen=True)
class TrackerConfig:
    odds_api_key: str
    region: str = "ca"
    bookmakers: str = ""
    season: int = 2024
    min_edge: float = 2.0
    min_ev: float = 0.02
    bankroll: float = 1000.0
    max_fraction_per_bet: float = 0.03


@dataclass(frozen=True)
class MarketSnapshot:
    """Single-cycle market snapshot to reuse across strategy profiles."""

    odds_events: list[dict[str, Any]]
    team_strength: dict[str, float]
