from __future__ import annotations

from collections import defaultdict
from typing import Any

from .data_sources import fetch_moneypuck_games, fetch_odds
from .math_utils import (
    american_to_decimal,
    american_to_implied_probability,
    expected_value_per_dollar,
    kelly_fraction,
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

        return {team: totals[team] / counts[team] for team in totals}


class EdgeScoringAgent:
    name = "edge-scoring-agent"

    @staticmethod
    def _estimate_win_probability(home_team: str, away_team: str, strength: dict[str, float]) -> tuple[float, float]:
        home_strength = strength.get(home_team)
        away_strength = strength.get(away_team)
        if home_strength is None or away_strength is None:
            return 0.5, 0.5
        denom = home_strength + away_strength
        home_prob = home_strength / denom if denom else 0.5
        return home_prob, 1 - home_prob

    def run(
        self,
        odds_events: list[dict[str, Any]],
        team_strength: dict[str, float],
        config: TrackerConfig,
    ) -> list[ValueCandidate]:
        candidates: list[ValueCandidate] = []
        for event in odds_events:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            commence = event.get("commence_time", "")
            home_prob_model, away_prob_model = self._estimate_win_probability(home_team, away_team, team_strength)

            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        side = outcome.get("name", "")
                        if side not in {home_team, away_team}:
                            continue
                        price = int(outcome.get("price"))
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
                                )
                            )

        return sorted(candidates, key=lambda c: c.expected_value_per_dollar, reverse=True)


class RiskAgent:
    name = "risk-agent"

    def run(self, candidates: list[ValueCandidate], config: TrackerConfig) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        for candidate in candidates:
            uncapped_stake = config.bankroll * candidate.kelly_fraction
            capped_stake = min(uncapped_stake, config.bankroll * config.max_fraction_per_bet)
            recommendations.append(
                {
                    "candidate": candidate,
                    "recommended_stake": round(capped_stake, 2),
                    "stake_fraction": round(capped_stake / config.bankroll, 4),
                }
            )
        return recommendations
