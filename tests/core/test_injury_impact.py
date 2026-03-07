"""Tests for injury tier classification and adjustment calculation."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _make_player_stats() -> list[dict]:
    """Build a realistic team roster: 12F + 6D + 2G sorted by TOI."""
    forwards = []
    for i, (name, pos, toi) in enumerate([
        ("Connor McDavid", "C", 1320),    # F1
        ("Leon Draisaitl", "C", 1280),    # F2
        ("Zach Hyman", "L", 1200),        # F3
        ("Ryan Nugent-Hopkins", "C", 1150),  # F4
        ("Evander Kane", "L", 1100),      # F5
        ("Viktor Arvidsson", "R", 1050),   # F6
        ("Connor Brown", "R", 900),        # F7 (bottom-6)
        ("Adam Henrique", "C", 850),       # F8
        ("Mattias Janmark", "C", 800),     # F9
        ("Derek Ryan", "C", 750),          # F10
        ("Warren Foegele", "L", 700),      # F11
        ("Corey Perry", "R", 650),         # F12
    ]):
        forwards.append({
            "player_id": 8470000 + i,
            "name": name,
            "position": pos,
            "toi_per_game": toi,
            "games_played": 60 - i,
            "points": 80 - i * 5,
        })

    defensemen = []
    for i, (name, toi) in enumerate([
        ("Evan Bouchard", 1500),   # D1
        ("Darnell Nurse", 1400),   # D2
        ("Mattias Ekholm", 1350),  # D3
        ("Brett Kulak", 1300),     # D4
        ("Cody Ceci", 1100),      # D5 (bottom-pair)
        ("Vincent Desharnais", 950),  # D6
    ]):
        defensemen.append({
            "player_id": 8480000 + i,
            "name": name,
            "position": "D",
            "toi_per_game": toi,
            "games_played": 65 - i,
            "points": 40 - i * 5,
        })

    goalies = [
        {
            "player_id": 8490001,
            "name": "Stuart Skinner",
            "position": "G",
            "toi_per_game": 0,
            "games_played": 50,
            "games_started": 48,
            "points": 0,
        },
        {
            "player_id": 8490002,
            "name": "Calvin Pickard",
            "position": "G",
            "toi_per_game": 0,
            "games_played": 25,
            "games_started": 22,
            "points": 0,
        },
    ]

    return forwards + defensemen + goalies


def _make_injury(
    *,
    team: str = "EDM",
    player_name: str = "Connor McDavid",
    position: str = "C",
    status: str = "Out",
    injury_type: str = "Upper Body",
) -> dict:
    """Build a single injury dict matching fetch_injuries() output."""
    return {
        "team": team,
        "player_name": player_name,
        "position": position,
        "status": status,
        "injury_type": injury_type,
        "return_date": "",
    }


# ---------------------------------------------------------------------------
# classify_player_tier tests
# ---------------------------------------------------------------------------

class TestClassifyPlayerTier:
    """Tests for tier classification by TOI rank."""

    def test_top6_forward(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Connor McDavid", "C", roster)
        assert tier == "top6_f"

    def test_bottom6_forward(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Connor Brown", "R", roster)
        assert tier == "bottom6_f"

    def test_top4_defenseman(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Evan Bouchard", "D", roster)
        assert tier == "top4_d"

    def test_bottom_defenseman(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Cody Ceci", "D", roster)
        assert tier == "bottom_d"

    def test_goalie_returns_starting_g(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Stuart Skinner", "G", roster)
        assert tier == "starting_g"

    def test_unknown_player_fallback_forward(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Unknown Player", "C", roster)
        assert tier == "bottom6_f"

    def test_unknown_player_fallback_defense(self):
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Unknown Player", "D", roster)
        assert tier == "bottom_d"

    def test_sixth_forward_is_top6(self):
        """The 6th forward by TOI should still be top6_f."""
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Viktor Arvidsson", "R", roster)
        assert tier == "top6_f"

    def test_fourth_defenseman_is_top4(self):
        """The 4th defenseman by TOI should still be top4_d."""
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tier = classify_player_tier("Brett Kulak", "D", roster)
        assert tier == "top4_d"


# ---------------------------------------------------------------------------
# calculate_injury_adjustment tests
# ---------------------------------------------------------------------------

class TestCalculateInjuryAdjustment:
    """Tests for adjustment calculation with GTD, cap, symmetry, goalie exclusion."""

    def _tiers_for(self, injuries: list[dict]) -> dict:
        """Build player_tiers dict by classifying against roster."""
        from app.core.injury_impact import classify_player_tier

        roster = _make_player_stats()
        tiers = {}
        for inj in injuries:
            tier = classify_player_tier(inj["player_name"], inj["position"], roster)
            tiers[(inj["team"], inj["player_name"])] = tier
        return tiers

    def test_single_top6_forward_away(self):
        """Single top-6 F injury on away team -> positive adjustment for home."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [_make_injury(team="EDM", player_name="Connor McDavid", position="C")]
        tiers = self._tiers_for(injuries)
        adj, players = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        # 2.0pp / 100 = 0.02
        assert adj == pytest.approx(0.02, abs=0.001)
        assert len(players) == 1

    def test_gtd_half_impact(self):
        """Day-To-Day status should apply 0.5 multiplier."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [_make_injury(team="EDM", player_name="Connor McDavid", position="C", status="Day-To-Day")]
        tiers = self._tiers_for(injuries)
        adj, _ = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        # 2.0 * 0.5 / 100 = 0.01
        assert adj == pytest.approx(0.01, abs=0.001)

    def test_dtd_status_also_half_impact(self):
        """DTD shorthand should also apply half impact."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [_make_injury(team="EDM", player_name="Connor McDavid", position="C", status="DTD")]
        tiers = self._tiers_for(injuries)
        adj, _ = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        assert adj == pytest.approx(0.01, abs=0.001)

    def test_cap_at_8pp(self):
        """5 top-6 F injuries = 10pp raw, should be capped to 8pp."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [
            _make_injury(team="EDM", player_name="Connor McDavid", position="C"),
            _make_injury(team="EDM", player_name="Leon Draisaitl", position="C"),
            _make_injury(team="EDM", player_name="Zach Hyman", position="L"),
            _make_injury(team="EDM", player_name="Ryan Nugent-Hopkins", position="C"),
            _make_injury(team="EDM", player_name="Evander Kane", position="L"),
        ]
        tiers = self._tiers_for(injuries)
        adj, _ = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        # Capped at 8pp / 100 = 0.08
        assert adj == pytest.approx(0.08, abs=0.001)

    def test_symmetrical_cancels_out(self):
        """Equal injuries on both teams -> net ~0."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [
            _make_injury(team="TOR", player_name="Connor McDavid", position="C"),
            _make_injury(team="EDM", player_name="Connor McDavid", position="C"),
        ]
        tiers = {
            ("TOR", "Connor McDavid"): "top6_f",
            ("EDM", "Connor McDavid"): "top6_f",
        }
        adj, _ = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        assert adj == pytest.approx(0.0, abs=0.001)

    def test_goalie_excluded_from_adjustment(self):
        """Solo goalie injury should give 0 adjustment (Phase 4 handles)."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [_make_injury(team="EDM", player_name="Stuart Skinner", position="G")]
        tiers = {("EDM", "Stuart Skinner"): "starting_g"}
        adj, players = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        assert adj == pytest.approx(0.0, abs=0.001)

    def test_goalie_in_display_list(self):
        """Goalie injury should appear in InjuredPlayer list for display."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [_make_injury(team="EDM", player_name="Stuart Skinner", position="G")]
        tiers = {("EDM", "Stuart Skinner"): "starting_g"}
        _, players = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        assert len(players) == 1
        assert players[0].player_name == "Stuart Skinner"
        assert players[0].tier == "starting_g"

    def test_no_injuries_returns_zero(self):
        """No injuries -> 0.0 adjustment, empty player list."""
        from app.core.injury_impact import calculate_injury_adjustment

        adj, players = calculate_injury_adjustment("TOR", "EDM", [], {})
        assert adj == 0.0
        assert players == []

    def test_home_team_injury_negative_adjustment(self):
        """Home team injury -> negative adjustment (home disadvantaged)."""
        from app.core.injury_impact import calculate_injury_adjustment

        injuries = [_make_injury(team="TOR", player_name="Connor McDavid", position="C")]
        tiers = {("TOR", "Connor McDavid"): "top6_f"}
        adj, _ = calculate_injury_adjustment("TOR", "EDM", injuries, tiers)
        assert adj == pytest.approx(-0.02, abs=0.001)


# ---------------------------------------------------------------------------
# build_player_tiers tests
# ---------------------------------------------------------------------------

class TestBuildPlayerTiers:
    """Tests for build_player_tiers with mock fetch function."""

    def test_builds_tiers_for_injured_teams(self):
        from app.core.injury_impact import build_player_tiers

        roster = _make_player_stats()
        mock_fetch = lambda team_code: roster

        injuries = [
            _make_injury(team="EDM", player_name="Connor McDavid", position="C"),
            _make_injury(team="EDM", player_name="Cody Ceci", position="D"),
        ]
        tiers = build_player_tiers(injuries, fetch_stats_fn=mock_fetch)

        assert tiers[("EDM", "Connor McDavid")] == "top6_f"
        assert tiers[("EDM", "Cody Ceci")] == "bottom_d"

    def test_only_fetches_for_injured_teams(self):
        """Should not fetch stats for teams without injuries."""
        from app.core.injury_impact import build_player_tiers

        fetched_teams = []

        def tracking_fetch(team_code):
            fetched_teams.append(team_code)
            return _make_player_stats()

        injuries = [_make_injury(team="EDM", player_name="Connor McDavid", position="C")]
        build_player_tiers(injuries, fetch_stats_fn=tracking_fetch)
        assert fetched_teams == ["EDM"]

    def test_caches_per_team(self):
        """Multiple injuries on same team should only fetch once."""
        from app.core.injury_impact import build_player_tiers

        fetch_count = [0]

        def counting_fetch(team_code):
            fetch_count[0] += 1
            return _make_player_stats()

        injuries = [
            _make_injury(team="EDM", player_name="Connor McDavid", position="C"),
            _make_injury(team="EDM", player_name="Evan Bouchard", position="D"),
        ]
        build_player_tiers(injuries, fetch_stats_fn=counting_fetch)
        assert fetch_count[0] == 1

    def test_empty_injuries_returns_empty(self):
        from app.core.injury_impact import build_player_tiers

        tiers = build_player_tiers([], fetch_stats_fn=lambda t: [])
        assert tiers == {}
