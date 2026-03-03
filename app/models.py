from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TeamMetrics:
    """Multi-factor team strength profile."""

    # Core share metrics (percentage-based, 0-1)
    xg_share: float = 0.5
    corsi_share: float = 0.5
    high_danger_share: float = 0.5
    shooting_pct: float = 0.08
    save_pct: float = 0.91
    pp_xg_per_60: float = 0.0
    pk_xg_against_per_60: float = 0.0
    recent_form: float = 0.5
    # Advanced metrics from MoneyPuck team game-by-game data
    score_adj_xg_share: float = 0.5       # Score-venue adjusted xG%
    flurry_adj_xg_share: float = 0.5      # Flurry-adjusted xG% (penalizes rebounds)
    fenwick_share: float = 0.5            # Fenwick% (unblocked shot attempts)
    hd_xg_share: float = 0.5             # High-danger xG share
    md_xg_share: float = 0.5             # Medium-danger xG share
    rebound_control: float = 0.5          # Rebound xG share (offensive rebounding)
    faceoff_pct: float = 0.5             # Faceoff win percentage
    takeaway_ratio: float = 0.5          # Takeaways / (takeaways + giveaways)
    dzone_giveaway_rate: float = 0.0     # D-zone giveaways per game (lower is better)
    # Composites & venue splits
    home_strength: float = 0.0
    away_strength: float = 0.0
    games_played: int = 0
    composite: float = 0.0
    # Goalie enrichment
    starter_save_pct: float = 0.0
    starter_gaa: float = 0.0


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
    # Tunable model parameters
    half_life: float = 30.0
    regression_k: int = 20
    home_advantage: float = 0.15
    logistic_k: float = 1.0
    goalie_impact: float = 1.5


@dataclass(frozen=True)
class MarketSnapshot:
    """Single-cycle market snapshot to reuse across strategy profiles."""

    odds_events: list[dict[str, Any]] = field(default_factory=list)
    team_strength: dict[str, TeamMetrics] = field(default_factory=dict)
    goalie_stats: list[dict[str, Any]] = field(default_factory=list)
