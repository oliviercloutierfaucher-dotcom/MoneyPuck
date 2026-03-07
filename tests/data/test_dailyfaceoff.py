"""Tests for DailyFaceoff starting goalies scraper (app.data.dailyfaceoff)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.data.dailyfaceoff import fetch_dailyfaceoff_starters, SLUG_TO_ABBREV


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NEXT_DATA_PAYLOAD = {
    "props": {
        "pageProps": {
            "data": [
                {
                    "homeGoalieName": "Jeremy Swayman",
                    "awayGoalieName": "Igor Shesterkin",
                    "homeNewsStrengthName": "Confirmed",
                    "awayNewsStrengthName": "Likely",
                    "homeGoalieSavePercentage": 0.905,
                    "awayGoalieSavePercentage": 0.921,
                    "homeTeamSlug": "boston-bruins",
                    "awayTeamSlug": "new-york-rangers",
                },
                {
                    "homeGoalieName": "Joseph Woll",
                    "awayGoalieName": "Samuel Montembeault",
                    "homeNewsStrengthName": None,
                    "awayNewsStrengthName": "Confirmed",
                    "homeGoalieSavePercentage": 0.918,
                    "awayGoalieSavePercentage": 0.912,
                    "homeTeamSlug": "toronto-maple-leafs",
                    "awayTeamSlug": "montreal-canadiens",
                },
            ],
        },
    },
}


def _build_html(next_data: dict) -> str:
    """Build a minimal HTML page with embedded __NEXT_DATA__."""
    json_str = json.dumps(next_data)
    return (
        "<html><head>"
        f'<script id="__NEXT_DATA__" type="application/json">{json_str}</script>'
        "</head><body></body></html>"
    )


def _mock_urlopen(html: str) -> MagicMock:
    """Create a mock urlopen return value from an HTML string."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = html.encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: fetch_dailyfaceoff_starters happy path
# ---------------------------------------------------------------------------


@patch("app.data.dailyfaceoff.urlopen")
def test_parses_next_data_json(mock_urlopen):
    """Extracts goalie data from __NEXT_DATA__ JSON."""
    html = _build_html(NEXT_DATA_PAYLOAD)
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert isinstance(result, list)
    assert len(result) == 2


@patch("app.data.dailyfaceoff.urlopen")
def test_returns_correct_goalie_names(mock_urlopen):
    """Goalie names extracted from __NEXT_DATA__ match source."""
    html = _build_html(NEXT_DATA_PAYLOAD)
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert result[0]["home_goalie"] == "Jeremy Swayman"
    assert result[0]["away_goalie"] == "Igor Shesterkin"


# ---------------------------------------------------------------------------
# Tests: status mapping
# ---------------------------------------------------------------------------


@patch("app.data.dailyfaceoff.urlopen")
def test_confirmed_status_maps_correctly(mock_urlopen):
    """Confirmed -> 'confirmed', Likely -> 'likely', None -> 'unconfirmed'."""
    html = _build_html(NEXT_DATA_PAYLOAD)
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert result[0]["home_status"] == "confirmed"
    assert result[0]["away_status"] == "likely"
    assert result[1]["home_status"] == "unconfirmed"
    assert result[1]["away_status"] == "confirmed"


# ---------------------------------------------------------------------------
# Tests: slug-to-abbrev mapping
# ---------------------------------------------------------------------------


def test_slug_to_abbrev_has_all_32_teams():
    """SLUG_TO_ABBREV dict covers all 32 NHL teams."""
    assert len(SLUG_TO_ABBREV) == 32


@patch("app.data.dailyfaceoff.urlopen")
def test_team_slugs_converted_to_abbreviations(mock_urlopen):
    """Team slugs from DailyFaceoff are converted to NHL abbreviations."""
    html = _build_html(NEXT_DATA_PAYLOAD)
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert result[0]["home_team"] == "BOS"
    assert result[0]["away_team"] == "NYR"
    assert result[1]["home_team"] == "TOR"
    assert result[1]["away_team"] == "MTL"


# ---------------------------------------------------------------------------
# Tests: save_pct pass-through
# ---------------------------------------------------------------------------


@patch("app.data.dailyfaceoff.urlopen")
def test_save_pct_included(mock_urlopen):
    """Save percentages from DailyFaceoff are passed through."""
    html = _build_html(NEXT_DATA_PAYLOAD)
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert abs(result[0]["home_save_pct"] - 0.905) < 1e-6
    assert abs(result[0]["away_save_pct"] - 0.921) < 1e-6


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


@patch("app.data.dailyfaceoff.urlopen")
def test_malformed_next_data_returns_empty(mock_urlopen):
    """Missing/malformed __NEXT_DATA__ returns empty list."""
    html = "<html><body>No script tag here</body></html>"
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert result == []


@patch("app.data.dailyfaceoff.urlopen")
def test_missing_props_returns_empty(mock_urlopen):
    """__NEXT_DATA__ with missing props.pageProps.data returns empty list."""
    html = _build_html({"props": {}})
    mock_urlopen.return_value = _mock_urlopen(html)

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert result == []


@patch("app.data.dailyfaceoff.urlopen")
def test_http_error_returns_empty(mock_urlopen):
    """HTTP timeout/error returns empty list."""
    from urllib.error import URLError

    mock_urlopen.side_effect = URLError("Connection timed out")

    result = fetch_dailyfaceoff_starters("2026-03-07")

    assert result == []
