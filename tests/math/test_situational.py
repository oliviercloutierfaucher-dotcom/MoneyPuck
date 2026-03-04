"""Phase 5: Situational factors adjustment tests."""

from datetime import date, timedelta

from app.math.situational import (
    TEAM_TIMEZONE,
    detect_rest_days,
    is_back_to_back,
    rest_adjustment,
    situational_adjustments,
    travel_adjustment,
)


# ---------------------------------------------------------------------------
# Helpers – synthetic game rows
# ---------------------------------------------------------------------------

def _make_game_row(home, away, game_date):
    """Build a minimal game row dict for situational tests."""
    if isinstance(game_date, date):
        game_date = game_date.isoformat()
    return {
        "homeTeamCode": home,
        "awayTeamCode": away,
        "gameDate": game_date,
    }


def _games_for_team(team, dates, opponent="OPP", home=True):
    """Generate a list of game rows where *team* played on each date."""
    rows = []
    for d in dates:
        if home:
            rows.append(_make_game_row(team, opponent, d))
        else:
            rows.append(_make_game_row(opponent, team, d))
    return rows


# ---------------------------------------------------------------------------
# 1. TEAM_TIMEZONE coverage
# ---------------------------------------------------------------------------

def test_team_timezone_has_all_teams():
    """TEAM_TIMEZONE should have at least 32 entries (all NHL teams)."""
    assert len(TEAM_TIMEZONE) >= 32


# ---------------------------------------------------------------------------
# 2–4. detect_rest_days
# ---------------------------------------------------------------------------

def test_detect_rest_days_one_day():
    """Team that played 2 days ago should have 1 rest day."""
    today = date(2026, 2, 15)
    two_ago = today - timedelta(days=2)
    rows = _games_for_team("MTL", [two_ago])
    rest = detect_rest_days("MTL", today, rows)
    assert rest == 1


def test_detect_rest_days_back_to_back():
    """Team that played yesterday with a game today should yield 0 rest days
    when asking about today's game (the prior game was just 1 day ago and the
    detect function counts calendar days minus one)."""
    today = date(2026, 2, 15)
    yesterday = today - timedelta(days=1)
    rows = _games_for_team("MTL", [yesterday, today])
    # Looking at the game on 'today', the most recent prior game is yesterday
    # => 0 rest days between them.
    rest = detect_rest_days("MTL", today, rows)
    assert rest == 0


def test_detect_rest_days_no_prior():
    """Team with no prior games returns the sentinel value 99."""
    today = date(2026, 2, 15)
    rest = detect_rest_days("MTL", today, [])
    assert rest == 99


def test_detect_rest_days_two_days():
    """Team that last played three days ago should have 2 rest days."""
    today = date(2026, 2, 15)
    three_ago = today - timedelta(days=3)
    rows = _games_for_team("TOR", [three_ago])
    rest = detect_rest_days("TOR", today, rows)
    assert rest == 2


def test_detect_rest_days_as_away_team():
    """detect_rest_days should find games where team was the away side too."""
    today = date(2026, 2, 15)
    two_ago = today - timedelta(days=2)
    rows = _games_for_team("MTL", [two_ago], home=False)
    rest = detect_rest_days("MTL", today, rows)
    assert rest == 1


# ---------------------------------------------------------------------------
# 5–6. is_back_to_back
# ---------------------------------------------------------------------------

def test_is_back_to_back_true():
    """0 rest days is a back-to-back."""
    assert is_back_to_back(0) is True


def test_is_back_to_back_false():
    """1 rest day is not a back-to-back."""
    assert is_back_to_back(1) is False


def test_is_back_to_back_sentinel():
    """99 (no prior games) is not a back-to-back."""
    assert is_back_to_back(99) is False


# ---------------------------------------------------------------------------
# 7–9. rest_adjustment
# ---------------------------------------------------------------------------

def test_rest_adj_b2b_vs_rested():
    """Home team on B2B (0 rest) vs rested away (2+ rest) should be roughly
    -0.04 (penalizing home)."""
    adj = rest_adjustment(0, 2)
    assert -0.08 < adj < -0.01  # negative because home is tired
    assert abs(adj - (-0.04)) < 0.02


def test_rest_adj_equal_rest():
    """Equal rest for both teams produces 0.0 adjustment."""
    assert rest_adjustment(1, 1) == 0.0
    assert rest_adjustment(2, 2) == 0.0
    assert rest_adjustment(0, 0) == 0.0


def test_rest_adj_rust():
    """Long rest (3+ days) should incur a slight rust penalty."""
    # Home rested 4 days vs away rested 1 day
    adj = rest_adjustment(4, 1)
    # The raw advantage of more rest should be reduced or even negative
    # due to rust, so the adjustment should be small or slightly negative.
    assert adj < 0.03  # not a large positive


def test_rest_adj_away_on_b2b():
    """Away team on B2B should give home a positive adjustment."""
    adj = rest_adjustment(2, 0)
    assert adj > 0.01


# ---------------------------------------------------------------------------
# 10–11. travel_adjustment
# ---------------------------------------------------------------------------

def test_travel_adj_same_timezone():
    """Teams in the same timezone should have no travel adjustment."""
    # NYR and NYI are both Eastern
    adj = travel_adjustment("NYR", "NYI")
    assert adj == 0.0


def test_travel_adj_cross_country():
    """VAN at BOS (Pacific -> Eastern, 3h diff) should give home advantage."""
    adj = travel_adjustment("BOS", "VAN")
    assert adj > 0.0  # home team benefits from away team's travel


def test_travel_adj_moderate():
    """A 1-hour timezone difference should produce a smaller adjustment than
    a 3-hour difference."""
    big = travel_adjustment("BOS", "VAN")     # 3h diff
    small = travel_adjustment("NYR", "CHI")   # ~1h diff
    assert big > small


def test_travel_adj_symmetric_magnitude():
    """Swapping home/away should flip the sign (or the adjustment always
    favors home, so the away-team penalty is reflected)."""
    adj_a = travel_adjustment("BOS", "VAN")
    adj_b = travel_adjustment("VAN", "BOS")
    # Both should be >= 0 (always helps home team)
    assert adj_a >= 0.0
    assert adj_b >= 0.0


# ---------------------------------------------------------------------------
# 12. situational_adjustments (combined)
# ---------------------------------------------------------------------------

def test_situational_combined():
    """Full situational_adjustments returns dict with all expected keys."""
    today = date(2026, 2, 15)
    yesterday = today - timedelta(days=1)
    three_ago = today - timedelta(days=3)

    rows = (
        _games_for_team("MTL", [yesterday]) +
        _games_for_team("TOR", [three_ago], home=False)
    )

    result = situational_adjustments("MTL", "TOR", today, rows)

    # Verify all expected keys are present
    assert "rest_adj" in result
    assert "travel_adj" in result
    assert "total_adj" in result
    assert "home_rest_days" in result
    assert "away_rest_days" in result
    assert "home_b2b" in result
    assert "away_b2b" in result


def test_situational_combined_values_sensible():
    """The total adjustment should be the sum of rest and travel parts."""
    today = date(2026, 2, 15)
    yesterday = today - timedelta(days=1)

    rows = _games_for_team("MTL", [yesterday])

    result = situational_adjustments("MTL", "TOR", today, rows)

    expected_total = result["rest_adj"] + result["travel_adj"]
    assert abs(result["total_adj"] - expected_total) < 1e-9


def test_situational_combined_b2b_flag():
    """When home team played yesterday, home_b2b should be True."""
    today = date(2026, 2, 15)
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)

    # MTL played yesterday AND today (back-to-back)
    rows = _games_for_team("MTL", [yesterday, today])

    result = situational_adjustments("MTL", "TOR", today, rows)

    assert result["home_b2b"] is True
    assert result["home_rest_days"] == 0
