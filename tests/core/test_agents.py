"""Tests for goalie confirmation integration in TeamStrengthAgent."""

from unittest.mock import patch

from app.core.agents import EdgeScoringAgent, TeamStrengthAgent
from app.core.models import TeamMetrics


# ---- Helper fixtures ----

def _make_team_gbg_row(team, opponent, venue="HOME", xg_pct=0.50, game_date="2026-01-15"):
    """Create a synthetic team game-by-game row."""
    return {
        "playerTeam": team,
        "opposingTeam": opponent,
        "situation": "all",
        "home_or_away": venue,
        "gameDate": game_date,
        "xGoalsPercentage": str(xg_pct),
        "corsiPercentage": "0.50",
        "fenwickPercentage": "0.50",
        "highDangerShotsFor": "5",
        "highDangerShotsAgainst": "5",
        "goalsFor": "3",
        "goalsAgainst": "2",
        "shotsOnGoalFor": "30",
        "shotsOnGoalAgainst": "28",
        "xGoalsFor": "2.5",
        "xGoalsAgainst": "2.0",
        "scoreVenueAdjustedxGoalsFor": "2.5",
        "scoreVenueAdjustedxGoalsAgainst": "2.0",
        "flurryAdjustedxGoalsFor": "2.4",
        "flurryAdjustedxGoalsAgainst": "2.1",
        "highDangerxGoalsFor": "1.5",
        "highDangerxGoalsAgainst": "1.2",
        "mediumDangerxGoalsFor": "0.8",
        "mediumDangerxGoalsAgainst": "0.7",
        "reboundxGoalsFor": "0.3",
        "reboundxGoalsAgainst": "0.2",
        "faceOffsWonFor": "28",
        "faceOffsWonAgainst": "25",
        "takeawaysFor": "8",
        "giveawaysFor": "6",
        "dZoneGiveawaysFor": "2",
    }


GOALIE_STATS = [
    {"player_name": "Jeremy Swayman", "team_code": "BOS", "games_played": 45, "save_pct": 0.915, "gaa": 2.50, "wins": 25},
    {"player_name": "Joonas Korpisalo", "team_code": "BOS", "games_played": 20, "save_pct": 0.895, "gaa": 3.10, "wins": 8},
    {"player_name": "Igor Shesterkin", "team_code": "NYR", "games_played": 50, "save_pct": 0.920, "gaa": 2.30, "wins": 30},
    {"player_name": "Jonathan Quick", "team_code": "NYR", "games_played": 15, "save_pct": 0.900, "gaa": 2.80, "wins": 7},
]

DF_STARTERS_CONFIRMED = [
    {
        "home_team": "BOS",
        "away_team": "NYR",
        "home_goalie": "Joonas Korpisalo",
        "away_goalie": "Igor Shesterkin",
        "home_status": "confirmed",
        "away_status": "confirmed",
        "home_save_pct": 0.895,
        "away_save_pct": 0.920,
    }
]


def _build_game_rows():
    """Build enough game rows for BOS and NYR to produce team metrics."""
    rows = []
    for i in range(5):
        d = f"2026-01-{10 + i:02d}"
        rows.append(_make_team_gbg_row("BOS", "NYR", "HOME", 0.52, d))
        rows.append(_make_team_gbg_row("NYR", "BOS", "AWAY", 0.48, d))
    return rows


# ---- Tests: confirmed starters ----

def test_confirmed_starter_uses_confirmed_save_pct():
    """When DailyFaceoff has confirmed starter, pipeline uses that goalie's save%."""
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    # With confirmed starters: BOS should use Korpisalo (0.895), not Swayman (0.915)
    result = agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=DF_STARTERS_CONFIRMED)

    assert "BOS" in result
    # Korpisalo's save_pct is 0.895 (confirmed backup)
    assert abs(result["BOS"].starter_save_pct - 0.895) < 0.001


def test_no_df_data_falls_back_to_gp_leader():
    """When no DailyFaceoff data, pipeline falls back to GP-leader (Swayman)."""
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    # Empty confirmed_starters -> GP-leader fallback
    result = agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=[])

    assert "BOS" in result
    # GP-leader is Swayman with save_pct 0.915
    assert abs(result["BOS"].starter_save_pct - 0.915) < 0.001


def test_no_confirmed_starters_param_defaults_to_gp_leader():
    """When confirmed_starters is not provided, falls back to GP-leader."""
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    # No confirmed_starters param at all
    result = agent.run(rows, goalie_stats=GOALIE_STATS)

    assert "BOS" in result
    assert abs(result["BOS"].starter_save_pct - 0.915) < 0.001


def test_starter_source_confirmed():
    """TeamMetrics.starter_source is 'confirmed' when DailyFaceoff has confirmation."""
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    result = agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=DF_STARTERS_CONFIRMED)

    assert result["BOS"].starter_source == "confirmed"
    assert result["NYR"].starter_source == "confirmed"


def test_starter_source_gp_leader_on_fallback():
    """TeamMetrics.starter_source is 'gp_leader' when falling back."""
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    result = agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=[])

    assert result["BOS"].starter_source == "gp_leader"
    assert result["NYR"].starter_source == "gp_leader"


def test_starter_source_likely():
    """TeamMetrics.starter_source is 'likely' when DailyFaceoff has likely status."""
    df_likely = [
        {
            "home_team": "BOS",
            "away_team": "NYR",
            "home_goalie": "Jeremy Swayman",
            "away_goalie": "Jonathan Quick",
            "home_status": "likely",
            "away_status": "likely",
            "home_save_pct": 0.915,
            "away_save_pct": 0.900,
        }
    ]
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    result = agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=df_likely)

    assert result["BOS"].starter_source == "likely"
    assert result["NYR"].starter_source == "likely"


def test_unconfirmed_status_falls_back_to_gp_leader():
    """When DailyFaceoff has 'unconfirmed' status, fall back to GP-leader."""
    df_unconfirmed = [
        {
            "home_team": "BOS",
            "away_team": "NYR",
            "home_goalie": "Joonas Korpisalo",
            "away_goalie": "Igor Shesterkin",
            "home_status": "unconfirmed",
            "away_status": "unconfirmed",
            "home_save_pct": 0.895,
            "away_save_pct": 0.920,
        }
    ]
    rows = _build_game_rows()
    agent = TeamStrengthAgent()

    result = agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=df_unconfirmed)

    # Unconfirmed -> should fall back to GP-leader
    assert result["BOS"].starter_source == "gp_leader"
    assert abs(result["BOS"].starter_save_pct - 0.915) < 0.001  # Swayman (GP leader)


# ---- Tests: injury adjustment in EdgeScoringAgent ----

class TestInjuryAdjustment:
    """Test injury_adj integration in EdgeScoringAgent."""

    def _build_strength(self):
        """Build minimal team strength dict for BOS and NYR."""
        rows = _build_game_rows()
        agent = TeamStrengthAgent()
        return agent.run(rows, goalie_stats=GOALIE_STATS, confirmed_starters=[])

    def test_injury_adj_positive_shifts_home_probability(self):
        """Positive injury_adj (away more hurt) increases home_prob."""
        strength = self._build_strength()
        base_hp, base_ap, _ = EdgeScoringAgent._estimate_win_probability(
            "BOS", "NYR", strength, injury_adj=0.0,
        )
        adj_hp, adj_ap, _ = EdgeScoringAgent._estimate_win_probability(
            "BOS", "NYR", strength, injury_adj=0.03,  # 3pp in probability units
        )
        assert adj_hp > base_hp
        assert adj_ap < base_ap

    def test_injury_adj_zero_no_change(self):
        """injury_adj=0.0 produces same result as without it."""
        strength = self._build_strength()
        hp1, ap1, c1 = EdgeScoringAgent._estimate_win_probability(
            "BOS", "NYR", strength,
        )
        hp2, ap2, c2 = EdgeScoringAgent._estimate_win_probability(
            "BOS", "NYR", strength, injury_adj=0.0,
        )
        assert hp1 == hp2
        assert ap1 == ap2

    def test_injury_adj_in_run_method(self):
        """EdgeScoringAgent.run() applies injury adjustment when injuries provided."""
        from unittest.mock import patch as _patch
        from app.core.models import TrackerConfig

        strength = self._build_strength()
        config = TrackerConfig(
            odds_api_key="test",
            season=2025,
            min_edge=0.0,
            min_ev=-999.0,
            max_edge=50.0,
        )
        odds_events = [{
            "home_team": "BOS",
            "away_team": "NYR",
            "commence_time": "2026-03-07T00:00:00Z",
            "bookmakers": [{
                "title": "TestBook",
                "key": "testbook",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "BOS", "price": -110},
                        {"name": "NYR", "price": +100},
                    ],
                }],
            }],
        }]

        # Mock injuries: NYR has a top-6 forward out
        injuries = [
            {"team": "NYR", "player_name": "Artemi Panarin", "position": "L", "status": "Out"},
        ]
        player_tiers = {("NYR", "Artemi Panarin"): "top6_f"}

        # Run with injuries
        agent = EdgeScoringAgent()
        candidates_with = agent.run(
            odds_events, strength, config, injuries=injuries, player_tiers=player_tiers,
        )

        # Run without injuries
        candidates_without = agent.run(
            odds_events, strength, config,
        )

        # Both should produce candidates (we set min_edge=0)
        assert len(candidates_with) > 0
        assert len(candidates_without) > 0

        # With NYR injured, BOS home prob should be higher, so BOS model_probability
        # should differ between the two runs
        bos_with = [c for c in candidates_with if c.side == "BOS"]
        bos_without = [c for c in candidates_without if c.side == "BOS"]
        if bos_with and bos_without:
            assert bos_with[0].model_probability != bos_without[0].model_probability
