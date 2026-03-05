"""Five-agent pipeline for NHL betting model.

MISSING DATA INPUTS — Agent 5 audit
------------------------------------
The following data sources are NOT currently incorporated but would
improve model accuracy and calibration:

1. **Injury data**: A team missing a top player (e.g. McDavid, Matthews)
   should have lower composite strength.  Currently the model has no
   roster awareness and treats a depleted team identically to a healthy
   one.  Impact: potentially 2-5 pp on individual game predictions.

2. **Line movement / sharp money tracking**: Sharp money movement on
   betting lines is one of the strongest short-term signals for game
   outcomes.  The model only compares its probability to the current
   line, ignoring *where the line opened* and *how it moved*.

3. **Confirmed starting goalies**: See nhl_api.infer_likely_starter()
   for details.  The current heuristic picks the GP leader, not the
   confirmed starter.

4. **Pace / era adjustment**: Raw xG values are not normalized across
   seasons.  If league-wide scoring rates shift (e.g. post-COVID
   changes, rule changes), historical xG comparisons are distorted.

5. **Schedule density beyond B2B**: Only back-to-back games are
   modeled in situational.py.  Fatiguing stretches like 3-in-4 nights
   or 4-in-6 nights are not detected.  Research suggests cumulative
   fatigue effects are meaningful (1-2 pp) beyond simple B2B.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import numpy as np

from app.data.data_sources import fetch_moneypuck_games, fetch_odds, fetch_team_game_by_game, safe_float
from app.logging_config import get_logger
from app.math.math_utils import (
    DEFAULT_METRIC_WEIGHTS,
    american_to_decimal,
    american_to_implied_probability,
    composite_strength,
    confidence_adjusted_kelly,
    days_between,
    edge_adjusted_confidence,
    expected_value_per_dollar,
    exponential_decay_weight,
    goalie_matchup_adjustment,
    kelly_fraction,
    logistic_win_probability,
    prediction_confidence,
    regress_to_mean,
)
from app.core.models import TeamMetrics, TrackerConfig, ValueCandidate
from app.data.nhl_api import fetch_goalie_stats, infer_likely_starter
from app.math.elo import EloTracker, build_elo_ratings
from app.math.situational import situational_adjustments

log = get_logger("agents")


# ---------------------------------------------------------------------------
# Agent 1 & 2: Data fetchers (unchanged API)
# ---------------------------------------------------------------------------

class MarketOddsAgent:
    name = "market-odds-agent"

    def run(self, config: TrackerConfig) -> list[dict[str, Any]]:
        return fetch_odds(config.odds_api_key, config.region, config.bookmakers or None)


class MoneyPuckDataAgent:
    name = "moneypuck-data-agent"

    def run(self, config: TrackerConfig) -> list[dict[str, str]]:
        """Fetch game data, preferring rich team game-by-game data."""
        try:
            rows = fetch_team_game_by_game(config.season)
            if rows:
                log.info("Using team game-by-game data (%d rows)", len(rows))
                return rows
        except Exception as exc:
            log.warning("Team game-by-game fetch failed, falling back to bulk CSV: %s", exc)
        return fetch_moneypuck_games(config.season)


# ---------------------------------------------------------------------------
# Agent 3: Multi-factor team strength (Phase 1)
# ---------------------------------------------------------------------------

class TeamStrengthAgent:
    name = "team-strength-agent"

    HALF_LIFE = 30.0   # days
    REGRESSION_K = 20  # games to weight 50/50 with prior

    def run(
        self,
        games_rows: list[dict[str, str]],
        config: TrackerConfig | None = None,
        goalie_stats: list[dict[str, Any]] | None = None,
    ) -> dict[str, TeamMetrics]:
        # Read tunable params from config (fall back to class defaults)
        half_life = config.half_life if config else self.HALF_LIFE
        regression_k = config.regression_k if config else self.REGRESSION_K
        goalie_impact = config.goalie_impact if config else 1.5

        today = date.today().isoformat()

        # ---- 1. Accumulate per-team, per-venue raw metric lists ----
        team_games: dict[str, list[dict]] = defaultdict(list)

        # Detect whether we have team-game-by-game data (has 'playerTeam')
        # or legacy bulk games.csv (has 'homeTeamCode')
        is_team_gbg = bool(games_rows and "playerTeam" in games_rows[0])

        if is_team_gbg:
            self._extract_team_gbg(games_rows, team_games, today, half_life)
        else:
            self._extract_legacy(games_rows, team_games, today, half_life)

        # ---- 2. Weighted averages per team ----
        METRIC_KEYS = list(DEFAULT_METRIC_WEIGHTS.keys())
        team_raw: dict[str, dict[str, float]] = {}
        team_home_raw: dict[str, dict[str, float]] = {}
        team_away_raw: dict[str, dict[str, float]] = {}
        team_game_counts: dict[str, int] = {}

        for team, games in team_games.items():
            weights = np.array([g["weight"] for g in games])
            total_w = weights.sum()
            if total_w == 0:
                continue
            team_game_counts[team] = len(games)

            raw = {}
            for key in METRIC_KEYS:
                vals = np.array([g[key] for g in games])
                raw[key] = float(np.average(vals, weights=weights))
            team_raw[team] = raw

            # Home split
            home_games = [g for g in games if g["venue"] == "home"]
            if home_games:
                hw = np.array([g["weight"] for g in home_games])
                team_home_raw[team] = {
                    key: float(np.average(
                        np.array([g[key] for g in home_games]), weights=hw
                    ))
                    for key in METRIC_KEYS
                }
            else:
                team_home_raw[team] = dict(raw)

            # Away split
            away_games = [g for g in games if g["venue"] == "away"]
            if away_games:
                aw = np.array([g["weight"] for g in away_games])
                team_away_raw[team] = {
                    key: float(np.average(
                        np.array([g[key] for g in away_games]), weights=aw
                    ))
                    for key in METRIC_KEYS
                }
            else:
                team_away_raw[team] = dict(raw)

        # ---- 3. Z-score normalize across teams ----
        teams = sorted(team_raw.keys())
        if not teams:
            return {}

        z_overall = self._z_score_all(team_raw, teams, METRIC_KEYS)
        z_home = self._z_score_all(team_home_raw, teams, METRIC_KEYS)
        z_away = self._z_score_all(team_away_raw, teams, METRIC_KEYS)

        # ---- 4. Rolling window composites (5g, 10g, momentum) ----
        rolling = self._compute_rolling_composites(
            team_games, teams, regression_k,
        )

        # ---- 5. Regression to mean & composite ----
        # Build goalie lookup: team_code -> starter dict
        goalie_lookup: dict[str, dict[str, Any]] = {}
        if goalie_stats:
            for team in teams:
                starter = infer_likely_starter(team, goalie_stats)
                if starter:
                    goalie_lookup[team] = starter

        result: dict[str, TeamMetrics] = {}
        for team in teams:
            n = team_game_counts.get(team, 0)
            regressed = {
                key: regress_to_mean(z_overall[team][key], n, regression_k, prior=0.0)
                for key in METRIC_KEYS
            }
            home_regressed = {
                key: regress_to_mean(z_home[team][key], n, regression_k, prior=0.0)
                for key in METRIC_KEYS
            }
            away_regressed = {
                key: regress_to_mean(z_away[team][key], n, regression_k, prior=0.0)
                for key in METRIC_KEYS
            }

            comp = composite_strength(regressed)
            home_comp = composite_strength(home_regressed)
            away_comp = composite_strength(away_regressed)

            # Goalie enrichment
            starter = goalie_lookup.get(team)
            s_save_pct = starter["save_pct"] if starter else 0.0
            s_gaa = starter["gaa"] if starter else 0.0

            raw = team_raw[team]
            roll = rolling.get(team, {})
            result[team] = TeamMetrics(
                xg_share=raw.get("xg_share", 0.5),
                corsi_share=raw.get("corsi_share", 0.5),
                high_danger_share=raw.get("high_danger_share", 0.5),
                shooting_pct=raw.get("shooting_pct", 0.08),
                save_pct=raw.get("save_pct", 0.91),
                pp_xg_per_60=raw.get("pp_xg_per_60", 0.0),
                pk_xg_against_per_60=raw.get("pk_xg_against_per_60", 0.0),
                recent_form=raw.get("xg_share", 0.5),
                # Advanced metrics
                score_adj_xg_share=raw.get("score_adj_xg_share", 0.5),
                flurry_adj_xg_share=raw.get("flurry_adj_xg_share", 0.5),
                fenwick_share=raw.get("fenwick_share", 0.5),
                hd_xg_share=raw.get("hd_xg_share", 0.5),
                md_xg_share=raw.get("md_xg_share", 0.5),
                rebound_control=raw.get("rebound_control", 0.5),
                faceoff_pct=raw.get("faceoff_pct", 0.5),
                takeaway_ratio=raw.get("takeaway_ratio", 0.5),
                dzone_giveaway_rate=raw.get("dzone_giveaway_rate", 0.0),
                # Composites
                home_strength=home_comp,
                away_strength=away_comp,
                games_played=n,
                composite=comp,
                # Rolling windows
                composite_5g=roll.get("composite_5g", 0.0),
                composite_10g=roll.get("composite_10g", 0.0),
                momentum=roll.get("momentum", 0.0),
                starter_save_pct=s_save_pct,
                starter_gaa=s_gaa,
            )

        return result

    @staticmethod
    def _extract_team_gbg(
        games_rows: list[dict[str, str]],
        team_games: dict[str, list[dict]],
        today: str,
        half_life: float,
    ) -> None:
        """Extract metrics from MoneyPuck team game-by-game CSVs (100+ columns)."""
        for row in games_rows:
            # Only use 'all' situation rows for team-level aggregation
            if row.get("situation", "all") != "all":
                continue

            team = row.get("playerTeam", row.get("team", ""))
            if not team:
                continue
            venue = row.get("home_or_away", "home").lower()
            game_date = row.get("gameDate", today)[:10]
            try:
                days_ago = days_between(game_date, today)
            except ValueError:
                days_ago = 0
            weight = exponential_decay_weight(days_ago, half_life)

            # Core share metrics
            xg_pct = safe_float(row, "xGoalsPercentage", 0.5)
            corsi_pct = safe_float(row, "corsiPercentage", 0.5)
            fenwick_pct = safe_float(row, "fenwickPercentage", 0.5)

            # Shots & goals
            hd_for = safe_float(row, "highDangerShotsFor")
            hd_against = safe_float(row, "highDangerShotsAgainst")
            goals_for = safe_float(row, "goalsFor")
            goals_against = safe_float(row, "goalsAgainst")
            shots_for = safe_float(row, "shotsOnGoalFor")
            shots_against = safe_float(row, "shotsOnGoalAgainst")

            # Advanced xG metrics (MoneyPuck team game-by-game exclusive)
            score_adj_xg_for = safe_float(row, "scoreVenueAdjustedxGoalsFor")
            score_adj_xg_against = safe_float(row, "scoreVenueAdjustedxGoalsAgainst")
            flurry_adj_xg_for = safe_float(row, "flurryAdjustedxGoalsFor")
            flurry_adj_xg_against = safe_float(row, "flurryAdjustedxGoalsAgainst")

            # Danger zone xG breakdowns
            hd_xg_for = safe_float(row, "highDangerxGoalsFor")
            hd_xg_against = safe_float(row, "highDangerxGoalsAgainst")
            md_xg_for = safe_float(row, "mediumDangerxGoalsFor")
            md_xg_against = safe_float(row, "mediumDangerxGoalsAgainst")

            # Rebound control
            rebound_xg_for = safe_float(row, "reboundxGoalsFor")
            rebound_xg_against = safe_float(row, "reboundxGoalsAgainst")

            # Faceoffs
            fo_won_for = safe_float(row, "faceOffsWonFor")
            fo_won_against = safe_float(row, "faceOffsWonAgainst")

            # Puck management
            takeaways_for = safe_float(row, "takeawaysFor")
            giveaways_for = safe_float(row, "giveawaysFor")
            dzone_ga_for = safe_float(row, "dZoneGiveawaysFor")

            xg_for_raw = safe_float(row, "xGoalsFor")
            xg_against_raw = safe_float(row, "xGoalsAgainst")

            # Compute share metrics
            hd_total = hd_for + hd_against
            hd_share = hd_for / hd_total if hd_total else 0.5

            score_adj_total = score_adj_xg_for + score_adj_xg_against
            score_adj_share = score_adj_xg_for / score_adj_total if score_adj_total else 0.5

            flurry_total = flurry_adj_xg_for + flurry_adj_xg_against
            flurry_share = flurry_adj_xg_for / flurry_total if flurry_total else 0.5

            hd_xg_total = hd_xg_for + hd_xg_against
            hd_xg_share = hd_xg_for / hd_xg_total if hd_xg_total else 0.5

            md_xg_total = md_xg_for + md_xg_against
            md_xg_share = md_xg_for / md_xg_total if md_xg_total else 0.5

            rebound_total = rebound_xg_for + rebound_xg_against
            rebound_share = rebound_xg_for / rebound_total if rebound_total else 0.5

            fo_total = fo_won_for + fo_won_against
            fo_pct = fo_won_for / fo_total if fo_total else 0.5

            ta_ga_total = takeaways_for + giveaways_for
            ta_ratio = takeaways_for / ta_ga_total if ta_ga_total else 0.5

            sh_pct = max(0.0, min(1.0, goals_for / shots_for)) if shots_for else 0.08
            sv_pct = max(0.0, min(1.0, 1 - (goals_against / shots_against))) if shots_against else 0.91

            entry = {
                "weight": weight,
                "game_date": game_date,
                "xg_share": xg_pct,
                "corsi_share": corsi_pct,
                "fenwick_share": fenwick_pct,
                "high_danger_share": hd_share,
                "score_adj_xg_share": score_adj_share,
                "flurry_adj_xg_share": flurry_share,
                "hd_xg_share": hd_xg_share,
                "md_xg_share": md_xg_share,
                "rebound_control": rebound_share,
                "faceoff_pct": fo_pct,
                "takeaway_ratio": ta_ratio,
                "dzone_giveaway_rate": dzone_ga_for,
                "shooting_pct": sh_pct,
                "save_pct": sv_pct,
                "pp_xg_per_60": xg_for_raw,
                "pk_xg_against_per_60": xg_against_raw,
                "venue": venue,
            }
            team_games[team].append(entry)

    @staticmethod
    def _extract_legacy(
        games_rows: list[dict[str, str]],
        team_games: dict[str, list[dict]],
        today: str,
        half_life: float,
    ) -> None:
        """Extract metrics from legacy bulk games.csv (backward compatible)."""
        for row in games_rows:
            home = row["homeTeamCode"]
            away = row["awayTeamCode"]
            game_date = row.get("gameDate", today)[:10]
            try:
                days_ago = days_between(game_date, today)
            except ValueError:
                days_ago = 0
            weight = exponential_decay_weight(days_ago, half_life)

            xg_pct = safe_float(row, "xGoalsPercentage", 0.5)
            corsi_pct = safe_float(row, "corsiPercentage", 0.5)
            fenwick_pct = safe_float(row, "fenwickPercentage", 0.5)
            hd_for = safe_float(row, "highDangerShotsFor")
            hd_against = safe_float(row, "highDangerShotsAgainst")
            goals_for = safe_float(row, "goalsFor")
            goals_against = safe_float(row, "goalsAgainst")
            shots_for = safe_float(row, "shotsOnGoalFor")
            shots_against = safe_float(row, "shotsOnGoalAgainst")
            xg_for = safe_float(row, "xGoalsFor")
            xg_against = safe_float(row, "xGoalsAgainst")

            hd_total = hd_for + hd_against
            hd_share = hd_for / hd_total if hd_total else 0.5
            sh_pct = max(0.0, min(1.0, goals_for / shots_for)) if shots_for else 0.08
            sv_pct = max(0.0, min(1.0, 1 - (goals_against / shots_against))) if shots_against else 0.91

            entry = {
                "weight": weight,
                "game_date": game_date,
                "xg_share": xg_pct,
                "corsi_share": corsi_pct,
                "fenwick_share": fenwick_pct,
                "high_danger_share": hd_share,
                "score_adj_xg_share": xg_pct,       # fallback: use raw xG
                "flurry_adj_xg_share": xg_pct,      # fallback: use raw xG
                "hd_xg_share": hd_share,             # fallback: use HD shot share
                "md_xg_share": 0.5,                  # no data
                "rebound_control": 0.5,              # no data
                "faceoff_pct": 0.5,                  # no data
                "takeaway_ratio": 0.5,               # no data
                "dzone_giveaway_rate": 0.0,          # no data
                "shooting_pct": sh_pct,
                "save_pct": sv_pct,
                "pp_xg_per_60": xg_for,
                "pk_xg_against_per_60": xg_against,
            }

            team_games[home].append({**entry, "venue": "home"})
            # Away team: flip share metrics
            away_sh = max(0.0, min(1.0, goals_against / shots_against)) if shots_against else 0.08
            away_sv = max(0.0, min(1.0, 1 - (goals_for / shots_for))) if shots_for else 0.91
            away_entry = {
                "weight": weight,
                "xg_share": 1 - xg_pct,
                "corsi_share": 1 - corsi_pct,
                "fenwick_share": 1 - fenwick_pct,
                "high_danger_share": 1 - hd_share,
                "score_adj_xg_share": 1 - xg_pct,
                "flurry_adj_xg_share": 1 - xg_pct,
                "hd_xg_share": 1 - hd_share,
                "md_xg_share": 0.5,
                "rebound_control": 0.5,
                "faceoff_pct": 0.5,
                "takeaway_ratio": 0.5,
                "dzone_giveaway_rate": 0.0,
                "shooting_pct": away_sh,
                "save_pct": away_sv,
                "pp_xg_per_60": xg_against,
                "pk_xg_against_per_60": xg_for,
                "venue": "away",
            }
            team_games[away].append(away_entry)

    @staticmethod
    def _z_score_all(
        raw: dict[str, dict[str, float]],
        teams: list[str],
        keys: list[str],
    ) -> dict[str, dict[str, float]]:
        """Z-score normalize each metric across all teams."""
        result: dict[str, dict[str, float]] = {t: {} for t in teams}
        for key in keys:
            vals = np.array([raw[t].get(key, 0.0) for t in teams])
            std = vals.std(ddof=1) if len(vals) > 1 else 1.0
            mean = vals.mean()
            if std == 0:
                std = 1.0
            for i, team in enumerate(teams):
                # Invert metrics where lower is better
                z = (vals[i] - mean) / std
                if key in ("pk_xg_against_per_60", "dzone_giveaway_rate"):
                    z = -z
                result[team][key] = float(z)
        return result

    # Rolling window metrics for recent form / momentum
    ROLLING_KEYS = [
        "xg_share", "fenwick_share", "hd_xg_share",
        "shooting_pct", "save_pct", "score_adj_xg_share",
    ]

    @classmethod
    def _compute_rolling_composites(
        cls,
        team_games: dict[str, list[dict]],
        teams: list[str],
        regression_k: int,
    ) -> dict[str, dict[str, float]]:
        """Compute 5-game and 10-game rolling composites + momentum.

        Returns {team: {"composite_5g": ..., "composite_10g": ..., "momentum": ...}}
        """
        rolling_raw_5: dict[str, dict[str, float]] = {}
        rolling_raw_10: dict[str, dict[str, float]] = {}
        game_counts_5: dict[str, int] = {}
        game_counts_10: dict[str, int] = {}

        for team in teams:
            games = team_games.get(team, [])
            # Sort by date descending (most recent first)
            sorted_games = sorted(games, key=lambda g: g.get("game_date", ""), reverse=True)

            for window, raw_dict, counts_dict in [
                (5, rolling_raw_5, game_counts_5),
                (10, rolling_raw_10, game_counts_10),
            ]:
                window_games = sorted_games[:window]
                counts_dict[team] = len(window_games)
                if not window_games:
                    raw_dict[team] = {k: 0.5 for k in cls.ROLLING_KEYS}
                    continue
                raw_dict[team] = {
                    k: sum(g[k] for g in window_games) / len(window_games)
                    for k in cls.ROLLING_KEYS
                }

        # Z-score rolling metrics across teams
        z_5 = cls._z_score_all(rolling_raw_5, teams, cls.ROLLING_KEYS)
        z_10 = cls._z_score_all(rolling_raw_10, teams, cls.ROLLING_KEYS)

        result: dict[str, dict[str, float]] = {}
        for team in teams:
            n5 = game_counts_5.get(team, 0)
            n10 = game_counts_10.get(team, 0)

            # Bayesian shrinkage (less regression for rolling — smaller k)
            reg_5 = {
                k: regress_to_mean(z_5[team][k], n5, max(1, regression_k // 6), prior=0.0)
                for k in cls.ROLLING_KEYS
            }
            reg_10 = {
                k: regress_to_mean(z_10[team][k], n10, max(1, regression_k // 4), prior=0.0)
                for k in cls.ROLLING_KEYS
            }

            comp_5 = composite_strength(reg_5)
            comp_10 = composite_strength(reg_10)

            result[team] = {
                "composite_5g": comp_5,
                "composite_10g": comp_10,
                "momentum": comp_5 - comp_10,
            }

        return result


# ---------------------------------------------------------------------------
# Agent 4: Edge scoring with logistic win probability (Phase 2)
# ---------------------------------------------------------------------------

class EdgeScoringAgent:
    name = "edge-scoring-agent"

    # Ensemble weight: how much to trust Elo vs our logistic model.
    # 0.0 = pure logistic, 1.0 = pure Elo.  0.25 = light Elo blend.
    ELO_WEIGHT = 0.25

    @staticmethod
    def _estimate_win_probability(
        home_team: str,
        away_team: str,
        strength: dict[str, TeamMetrics],
        sit_adj: float = 0.0,
        goalie_adj: float = 0.0,
        home_advantage: float = 0.14,
        logistic_k: float = 0.9,
        elo_tracker: EloTracker | None = None,
        elo_weight: float = 0.25,
    ) -> tuple[float, float, float]:
        """Returns (home_prob, away_prob, confidence).

        *sit_adj* is a situational probability adjustment (rest, travel).
        *goalie_adj* is a goalie matchup adjustment (save% differential).
        Both are applied as probability deltas from the home team's perspective.
        *elo_tracker* if provided, blends Elo probability with logistic model.
        """
        home_metrics = strength.get(home_team)
        away_metrics = strength.get(away_team)
        if home_metrics is None or away_metrics is None:
            missing = [t for t, m in [(home_team, home_metrics), (away_team, away_metrics)] if m is None]
            log.warning("Missing strength data for %s — defaulting to 50/50", missing)
            return 0.5, 0.5, 0.0

        home_z = home_metrics.home_strength
        away_z = away_metrics.away_strength

        logistic_home, _ = logistic_win_probability(
            home_z, away_z, home_advantage=home_advantage, k=logistic_k
        )

        # Ensemble with Elo if available
        if elo_tracker is not None:
            elo_home = elo_tracker.predict(home_team, away_team)
            home_prob = (1 - elo_weight) * logistic_home + elo_weight * elo_home
        else:
            home_prob = logistic_home

        # Momentum adjustment from rolling windows
        momentum_adj = 0.0
        if home_metrics.composite_5g != 0.0 or away_metrics.composite_5g != 0.0:
            momentum_adj = (home_metrics.momentum - away_metrics.momentum) * 0.02

        # Apply situational + goalie + momentum adjustments
        # goalie_adj is in percentage points (e.g. 3.0 = 3pp), convert to probability
        total_adj = sit_adj + goalie_adj / 100.0 + momentum_adj
        home_prob = max(0.01, min(0.99, home_prob + total_adj))
        away_prob = 1.0 - home_prob

        conf = prediction_confidence(
            home_metrics.games_played, away_metrics.games_played
        )
        return home_prob, away_prob, conf

    def run(
        self,
        odds_events: list[dict[str, Any]],
        team_strength: dict[str, TeamMetrics],
        config: TrackerConfig,
        games_rows: list[dict[str, str]] | None = None,
        elo_tracker: EloTracker | None = None,
    ) -> list[ValueCandidate]:
        candidates: list[ValueCandidate] = []
        for event in odds_events:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            commence = event.get("commence_time", "")

            # Phase 5: situational adjustments (rest, travel)
            sit_adj = 0.0
            if games_rows:
                game_date = commence[:10] if commence else ""
                if game_date:
                    sit = situational_adjustments(
                        home_team, away_team, game_date, games_rows
                    )
                    sit_adj = sit.get("total_adj", 0.0)

            # Goalie matchup adjustment
            g_adj = 0.0
            home_m = team_strength.get(home_team)
            away_m = team_strength.get(away_team)
            if home_m and away_m and home_m.starter_save_pct and away_m.starter_save_pct:
                g_adj = goalie_matchup_adjustment(
                    home_m.starter_save_pct,
                    away_m.starter_save_pct,
                    config.goalie_impact,
                )

            home_prob_model, away_prob_model, conf = (
                self._estimate_win_probability(
                    home_team, away_team, team_strength, sit_adj, g_adj,
                    home_advantage=config.home_advantage,
                    logistic_k=config.logistic_k,
                    elo_tracker=elo_tracker,
                )
            )

            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        side = outcome.get("name", "")
                        if side not in {home_team, away_team}:
                            continue
                        try:
                            price = int(outcome.get("price", 0))
                        except (ValueError, TypeError):
                            log.warning("Skipping outcome with invalid price: %s", outcome.get("price"))
                            continue
                        if price == 0:
                            continue
                        decimal_odds = american_to_decimal(price)
                        implied = american_to_implied_probability(price)
                        model_p = home_prob_model if side == home_team else away_prob_model
                        edge_pp = (model_p - implied) * 100
                        ev = expected_value_per_dollar(model_p, decimal_odds)
                        kelly = kelly_fraction(model_p, decimal_odds)

                        # Hard cap: reject edges that are almost certainly model artifacts
                        max_edge = getattr(config, "max_edge", 10.0)
                        if edge_pp > max_edge:
                            log.info(
                                "Rejected %s %s @ %s: edge %.1fpp exceeds cap %.1fpp",
                                side, home_team if side == home_team else away_team,
                                bookmaker.get("title", "?"), edge_pp, max_edge,
                            )
                            continue

                        if edge_pp >= config.min_edge and ev >= config.min_ev:
                            # Penalize suspiciously large edges
                            adj_conf = edge_adjusted_confidence(conf, edge_pp)
                            candidates.append(
                                ValueCandidate(
                                    commence_time_utc=commence,
                                    home_team=home_team,
                                    away_team=away_team,
                                    side=side,
                                    sportsbook=bookmaker.get("title", "unknown"),
                                    american_odds=price,
                                    decimal_odds=decimal_odds,
                                    implied_probability=implied,
                                    model_probability=model_p,
                                    edge_probability_points=edge_pp,
                                    expected_value_per_dollar=ev,
                                    kelly_fraction=kelly,
                                    confidence=adj_conf,
                                )
                            )

        return sorted(candidates, key=lambda c: c.expected_value_per_dollar, reverse=True)


# ---------------------------------------------------------------------------
# Agent 5: Line shopping (Phase 3)
# ---------------------------------------------------------------------------

class LineShoppingAgent:
    """For each game+side, keep only the best available odds across books."""

    name = "line-shopping-agent"

    @staticmethod
    def best_lines(candidates: list[ValueCandidate]) -> list[ValueCandidate]:
        best: dict[tuple[str, str, str], ValueCandidate] = {}
        for c in candidates:
            key = (c.commence_time_utc, c.home_team + c.away_team, c.side)
            if key not in best or c.decimal_odds > best[key].decimal_odds:
                best[key] = c
        return sorted(best.values(), key=lambda c: c.expected_value_per_dollar, reverse=True)


# ---------------------------------------------------------------------------
# Agent 6: Smart risk & bankroll management (Phase 3)
# ---------------------------------------------------------------------------

class RiskAgent:
    name = "risk-agent"

    def run(self, candidates: list[ValueCandidate], config: TrackerConfig) -> list[dict[str, Any]]:
        # Best-line filter: one line per game+side
        best = LineShoppingAgent.best_lines(candidates)

        recommendations: list[dict[str, Any]] = []
        nightly_spent: dict[str, float] = defaultdict(float)

        for candidate in best:
            game_date = candidate.commence_time_utc[:10]
            remaining = (
                config.bankroll * config.max_nightly_exposure
                - nightly_spent[game_date]
            )
            if remaining <= 0:
                continue

            # Confidence-adjusted fractional Kelly
            adj_kelly = confidence_adjusted_kelly(
                candidate.model_probability,
                candidate.decimal_odds,
                candidate.confidence,
                config.kelly_fraction,
            )
            raw_stake = config.bankroll * adj_kelly
            capped_stake = min(
                raw_stake,
                config.bankroll * config.max_fraction_per_bet,
                remaining,
            )
            capped_stake = max(capped_stake, 0.0)
            nightly_spent[game_date] += capped_stake

            recommendations.append(
                {
                    "candidate": candidate,
                    "recommended_stake": round(capped_stake, 2),
                    "stake_fraction": round(capped_stake / config.bankroll, 4) if config.bankroll else 0.0,
                }
            )
        return recommendations
