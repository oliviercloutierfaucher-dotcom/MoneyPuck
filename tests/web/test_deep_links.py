"""Tests for sportsbook deep link generation."""

from __future__ import annotations

from app.web.deep_links import SPORTSBOOK_URLS, TEAM_SLUGS, build_sportsbook_url


class TestSportsbookUrls:
    """Test the SPORTSBOOK_URLS mapping."""

    def test_known_books_have_urls(self):
        known_keys = ["draftkings", "fanduel", "betmgm", "bet365", "pinnacle", "caesars"]
        for key in known_keys:
            assert key in SPORTSBOOK_URLS, f"Missing URL for {key}"
            assert SPORTSBOOK_URLS[key].startswith("https://"), f"URL for {key} should be HTTPS"

    def test_canadian_books_present(self):
        ca_keys = ["bet365", "betway", "bet99", "fanduel", "draftkings", "betmgm", "pinnacle"]
        for key in ca_keys:
            assert key in SPORTSBOOK_URLS, f"Missing Canadian book {key}"

    def test_us_books_present(self):
        us_keys = ["caesars", "draftkings", "fanduel", "betmgm"]
        for key in us_keys:
            assert key in SPORTSBOOK_URLS, f"Missing US book {key}"


class TestTeamSlugs:
    """Test the TEAM_SLUGS mapping."""

    def test_all_32_teams(self):
        assert len(TEAM_SLUGS) == 32

    def test_slug_format(self):
        for code, slug in TEAM_SLUGS.items():
            assert len(code) == 3, f"Team code {code} should be 3 chars"
            assert "-" in slug, f"Slug {slug} should be hyphenated"
            assert slug == slug.lower(), f"Slug {slug} should be lowercase"

    def test_known_slugs(self):
        assert TEAM_SLUGS["TOR"] == "toronto-maple-leafs"
        assert TEAM_SLUGS["MTL"] == "montreal-canadiens"
        assert TEAM_SLUGS["EDM"] == "edmonton-oilers"
        assert TEAM_SLUGS["VGK"] == "vegas-golden-knights"


class TestBuildSportsbookUrl:
    """Test build_sportsbook_url()."""

    def test_known_book_returns_url(self):
        url = build_sportsbook_url("draftkings", "TOR", "MTL", "2026-03-05T00:00:00Z")
        assert url.startswith("https://")
        assert "draftkings" in url

    def test_unknown_book_returns_empty(self):
        url = build_sportsbook_url("unknown_book_xyz", "TOR", "MTL", "2026-03-05T00:00:00Z")
        assert url == ""

    def test_empty_key_returns_empty(self):
        url = build_sportsbook_url("", "TOR", "MTL", "2026-03-05T00:00:00Z")
        assert url == ""

    def test_no_team_args_still_works(self):
        url = build_sportsbook_url("fanduel")
        assert url.startswith("https://")

    def test_all_mapped_books_return_urls(self):
        for key in SPORTSBOOK_URLS:
            url = build_sportsbook_url(key)
            assert url, f"build_sportsbook_url should return URL for {key}"
