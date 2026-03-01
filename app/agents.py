from __future__ import annotations

from collections import defaultdict
from typing import Any

from .data_sources import fetch_moneypuck_games, fetch_odds
from .math_utils import (
    american_to_decimal,
    american_to_implied_probability,
    clamp,
    expected_value_per_dollar,
    kelly_fraction,
    no_vig_two_way_probabilities,
)
from .models import TrackerConfig, ValueCandidate


class MarketOddsAgent:
    name = "market-odds-agent"

    def run(self, config: TrackerConfig) -> list[dict[str, Any]]:
        return fetch_odds(config.odds_api_key, config.region, config.bookmakers or None)


class MoneyPuckDataAgent:
    name = "moneypuck-data-agent"

    def run(self, config: TrackerConfig) -> list[dict[str, str]]:
        return fetch_moneypuck_games(config.season)


class TeamStrengthAgent:
    name = "team-strength-agent"

    def run(self, games_rows: list[dict[str, str]]) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)

        for row in games_rows:
            home = row["homeTeamCode"]
            away = row["awayTeamCode"]
            xg_home = float(row["xGoalsPercentage"])
            xg_away = 1 - xg_home
            totals[home] += xg_home
            counts[home] += 1
            totals[away] += xg_away
            counts[away] += 1

        # Bayesian shrink toward 50% to reduce early-season noise.
        prior_games = 12
        strength: dict[str, float] = {}
        for team in totals:
            raw = totals[team] / counts[team]
            strength[team] = ((raw * counts[team]) + (0.5 * prior_games)) / (counts[team] + prior_games)

        return strength


class EdgeScoringAgent:
    name = "edge-scoring-agent"

    @staticmethod
    def _estimate_win_probability(
        home_team: str,
        away_team: str,
        strength: dict[str, float],
        config: TrackerConfig,
    ) -> tuple[float, float]:
        home_strength = strength.get(home_team)
        away_strength = strength.get(away_team)
        if home_strength is None or away_strength is None:
            return 0.5, 0.5

        denom = home_strength + away_strength
        home_raw = home_strength / denom if denom else 0.5
        home_adjusted = clamp(home_raw + (config.home_advantage_pp / 100), 0.03, 0.97)
        return home_adjusted, 1 - home_adjusted

    @staticmethod
    def _extract_market_views(
        event: dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> tuple[dict[str, tuple[int, str]], dict[str, float]]:
        best_lines: dict[str, tuple[int, str]] = {}
        no_vig_accumulator: dict[str, list[float]] = {home_team: [], away_team: []}

        for bookmaker in event.get("bookmakers", []):
            book_name = bookmaker.get("title", "unknown")
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue

                outcomes = market.get("outcomes", [])
                two_way: dict[str, int] = {}
                for outcome in outcomes:
                    side = outcome.get("name", "")
                    if side not in {home_team, away_team}:
                        continue
                    price = int(outcome.get("price"))
                    two_way[side] = price

                    if side not in best_lines or price > best_lines[side][0]:
                        best_lines[side] = (price, book_name)

                if home_team in two_way and away_team in two_way:
                    home_implied = american_to_implied_probability(two_way[home_team])
                    away_implied = american_to_implied_probability(two_way[away_team])
                    home_fair, away_fair = no_vig_two_way_probabilities(home_implied, away_implied)
                    no_vig_accumulator[home_team].append(home_fair)
                    no_vig_accumulator[away_team].append(away_fair)

        consensus = {
            home_team: sum(no_vig_accumulator[home_team]) / len(no_vig_accumulator[home_team])
            if no_vig_accumulator[home_team]
            else 0.5,
            away_team: sum(no_vig_accumulator[away_team]) / len(no_vig_accumulator[away_team])
            if no_vig_accumulator[away_team]
            else 0.5,
        }
        return best_lines, consensus

    def run(
        self,
        odds_events: list[dict[str, Any]],
        team_strength: dict[str, float],
        config: TrackerConfig,
    ) -> list[ValueCandidate]:
        candidates: list[ValueCandidate] = []
        blend = clamp(config.market_blend, 0.0, 0.85)

        for event in odds_events:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            if not home_team or not away_team:
                continue

            commence = event.get("commence_time", "")
            model_home, model_away = self._estimate_win_probability(home_team, away_team, team_strength, config)
            best_lines, consensus = self._extract_market_views(event, home_team, away_team)

            model_home = (1 - blend) * model_home + blend * consensus.get(home_team, 0.5)
            model_away = 1 - model_home

            for side in (home_team, away_team):
                line = best_lines.get(side)
                if not line:
                    continue
                price, sportsbook = line

                decimal_odds = american_to_decimal(price)
                implied = american_to_implied_probability(price)
                no_vig = consensus.get(side, 0.5)
                model_p = model_home if side == home_team else model_away
                edge_pp = (model_p - implied) * 100
                ev = expected_value_per_dollar(model_p, decimal_odds)
                confidence = abs(model_p - no_vig) * 100
                kelly = kelly_fraction(model_p, decimal_odds)

                if edge_pp >= config.min_edge and ev >= config.min_ev:
                    candidates.append(
                        ValueCandidate(
                            commence_time_utc=commence,
                            home_team=home_team,
                            away_team=away_team,
                            side=side,
                            sportsbook=sportsbook,
                            american_odds=price,
                            decimal_odds=decimal_odds,
                            implied_probability=implied,
                            no_vig_probability=no_vig,
                            model_probability=model_p,
                            confidence_score=confidence,
                            edge_probability_points=edge_pp,
                            expected_value_per_dollar=ev,
                            kelly_fraction=kelly,
                        )
                    )

        return sorted(candidates, key=lambda c: (c.expected_value_per_dollar, c.confidence_score), reverse=True)


class RiskAgent:
    name = "risk-agent"

    def run(self, candidates: list[ValueCandidate], config: TrackerConfig) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        scale = clamp(config.kelly_scale, 0.05, 1.0)
        for candidate in candidates:
            confidence_multiplier = clamp(candidate.confidence_score / 10, 0.35, 1.0)
            scaled_kelly = candidate.kelly_fraction * scale * confidence_multiplier
            uncapped_stake = config.bankroll * scaled_kelly
            capped_stake = min(uncapped_stake, config.bankroll * config.max_fraction_per_bet)
            recommendations.append(
                {
                    "candidate": candidate,
                    "recommended_stake": round(capped_stake, 2),
                    "stake_fraction": round(capped_stake / config.bankroll, 4),
                }
            )
        return recommendations
