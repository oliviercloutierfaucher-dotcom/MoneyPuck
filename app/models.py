from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TeamMetrics:
    """Multi-factor team strength profile."""

    xg_share: float = 0.5
    corsi_share: float = 0.5
    high_danger_share: float = 0.5
    shooting_pct: float = 0.08
    save_pct: float = 0.91
    pp_xg_per_60: float = 0.0
    pk_xg_against_per_60: float = 0.0
    recent_form: float = 0.5
    home_strength: float = 0.0
    away_strength: float = 0.0
    games_played: int = 0
    composite: float = 0.0


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
    confidence: float = 1.0


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
    kelly_fraction: float = 0.5
    max_nightly_exposure: float = 0.15
    persist: bool = False


@dataclass(frozen=True)
class MarketSnapshot:
    """Single-cycle market snapshot to reuse across strategy profiles."""

    odds_events: list[dict[str, Any]] = field(default_factory=list)
    team_strength: dict[str, TeamMetrics] = field(default_factory=dict)
