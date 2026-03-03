from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import numpy as np

from .data_sources import fetch_moneypuck_games, fetch_odds, safe_float
from .logging_config import get_logger
from .math_utils import (
    DEFAULT_METRIC_WEIGHTS,
    american_to_decimal,
    american_to_implied_probability,
    composite_strength,
    confidence_adjusted_kelly,
    days_between,
    expected_value_per_dollar,
    exponential_decay_weight,
    goalie_matchup_adjustment,
    kelly_fraction,
    logistic_win_probability,
    prediction_confidence,
    regress_to_mean,
)
from .models import TeamMetrics, TrackerConfig, ValueCandidate
from .nhl_api import fetch_goalie_stats, infer_likely_starter
from .situational import situational_adjustments

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
            hd_for = safe_float(row, "highDangerShotsFor")
            hd_against = safe_float(row, "highDangerShotsAgainst")
            goals_for = safe_float(row, "goalsFor")
            goals_against = safe_float(row, "goalsAgainst")
            shots_for = safe_float(row, "shotsOnGoalFor")
            shots_against = safe_float(row, "shotsOnGoalAgainst")
            xg_for = safe_float(row, "xGoalsFor")
            xg_against = safe_float(row, "xGoalsAgainst")
            pim_for = safe_float(row, "penaltiesFor")
            pim_against = safe_float(row, "penaltiesAgainst")

            hd_total = hd_for + hd_against
            hd_share = hd_for / hd_total if hd_total else 0.5
            sh_pct = goals_for / shots_for if shots_for else 0.08
            sv_pct = 1 - (goals_against / shots_against) if shots_against else 0.91
            pp_xg = xg_for  # proxy (full-game xG offensive rate)
            pk_xg_a = xg_against

            entry = {
                "weight": weight,
                "xg_share": xg_pct,
                "corsi_share": corsi_pct,
                "high_danger_share": hd_share,
                "shooting_pct": sh_pct,
                "save_pct": sv_pct,
                "pp_xg_per_60": pp_xg,
                "pk_xg_against_per_60": pk_xg_a,
            }

            # Home team sees these metrics as-is
            team_games[home].append({**entry, "venue": "home"})
            # Away team: flip share metrics
            away_entry = {
                "weight": weight,
                "xg_share": 1 - xg_pct,
                "corsi_share": 1 - corsi_pct,
                "high_danger_share": 1 - hd_share,
                "shooting_pct": goals_against / shots_against if shots_against else 0.08,
                "save_pct": 1 - (goals_for / shots_for) if shots_for else 0.91,
                "pp_xg_per_60": xg_against,
                "pk_xg_against_per_60": xg_for,
                "venue": "away",
            }
            team_games[away].append(away_entry)

        # ---- 2. Weighted averages per team ----
        METRIC_KEYS = [
            "xg_share", "corsi_share", "high_danger_share",
            "shooting_pct", "save_pct", "pp_xg_per_60", "pk_xg_against_per_60",
        ]
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

        # ---- 4. Regression to mean & composite ----
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
            result[team] = TeamMetrics(
                xg_share=raw["xg_share"],
                corsi_share=raw["corsi_share"],
                high_danger_share=raw["high_danger_share"],
                shooting_pct=raw["shooting_pct"],
                save_pct=raw["save_pct"],
                pp_xg_per_60=raw["pp_xg_per_60"],
                pk_xg_against_per_60=raw["pk_xg_against_per_60"],
                recent_form=raw["xg_share"],  # decay-weighted xG is the recent form
                home_strength=home_comp,
                away_strength=away_comp,
                games_played=n,
                composite=comp,
                starter_save_pct=s_save_pct,
                starter_gaa=s_gaa,
            )

        return result

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
                # Invert pk_xg_against_per_60 (lower is better)
                z = (vals[i] - mean) / std
                if key == "pk_xg_against_per_60":
                    z = -z
                result[team][key] = float(z)
        return result


# ---------------------------------------------------------------------------
# Agent 4: Edge scoring with logistic win probability (Phase 2)
# ---------------------------------------------------------------------------

class EdgeScoringAgent:
    name = "edge-scoring-agent"

    @staticmethod
    def _estimate_win_probability(
        home_team: str,
        away_team: str,
        strength: dict[str, TeamMetrics],
        sit_adj: float = 0.0,
        goalie_adj: float = 0.0,
        home_advantage: float = 0.15,
        logistic_k: float = 1.0,
    ) -> tuple[float, float, float]:
        """Returns (home_prob, away_prob, confidence).

        *sit_adj* is a situational probability adjustment (rest, travel).
        *goalie_adj* is a goalie matchup adjustment (save% differential).
        Both are applied as probability deltas from the home team's perspective.
        """
        home_metrics = strength.get(home_team)
        away_metrics = strength.get(away_team)
        if home_metrics is None or away_metrics is None:
            return 0.5, 0.5, 0.0

        home_z = home_metrics.home_strength
        away_z = away_metrics.away_strength

        home_prob, away_prob = logistic_win_probability(
            home_z, away_z, home_advantage=home_advantage, k=logistic_k
        )
        # Apply situational + goalie adjustments
        total_adj = sit_adj + goalie_adj
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

                        if edge_pp >= config.min_edge and ev >= config.min_ev:
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
                                    confidence=conf,
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
