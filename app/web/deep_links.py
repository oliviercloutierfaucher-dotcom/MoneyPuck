"""Sportsbook deep link generation for NHL games."""

from __future__ import annotations


# Maps The Odds API bookmaker key -> NHL section URL
SPORTSBOOK_URLS: dict[str, str] = {
    # Canadian books
    "bet365": "https://www.bet365.com/#/AS/HO/",
    "betway": "https://betway.com/sports/cat/ice-hockey/league/nhl",
    "bet99": "https://bet99.com/sports/hockey/nhl",
    "fanduel": "https://sportsbook.fanduel.com/navigation/nhl",
    "draftkings": "https://sportsbook.draftkings.com/leagues/hockey/nhl",
    "betmgm": "https://sports.betmgm.com/en/sports/hockey-17",
    "pinnacle": "https://www.pinnacle.com/en/hockey/nhl/matchups",
    "betvictorca": "https://www.betvictor.com/en-ca/sports/ice-hockey",
    "pointsbetus": "https://pointsbet.com/sports/icehockey/NHL",
    "betrivers": "https://betrivers.com/?page=sportsbook#sports/hockey",
    "betano": "https://www.betano.ca/sport/hockey/",
    "northstar": "https://www.northstarbets.ca/sport/hockey",
    "espacejeuxca": "https://www.espacejeux.com/en/sports/hockey",
    # US books
    "caesars": "https://www.caesars.com/sportsbook-and-casino/sport/hockey",
    "wynnbet": "https://bet.wynnbet.com/sports/hockey",
    "twinspires": "https://www.twinspires.com/sportsbook/hockey",
    "williamhill_us": "https://www.williamhill.com/us/co/bet/sports/hockey",
    "unibet_us": "https://www.unibet.com/sports/hockey",
    # Ontario books
    "williamhill": "https://www.williamhill.com/sports/ice-hockey",
    "unibet": "https://www.unibet.com/sports/hockey",
    "thescorebet": "https://thescore.bet/sport/hockey",
    "coolbet": "https://www.coolbet.com/en/sports/ice-hockey",
    "888sport": "https://www.888sport.com/ice-hockey/",
}

# Maps 3-letter team code -> URL-friendly slug
TEAM_SLUGS: dict[str, str] = {
    "ANA": "anaheim-ducks",
    "BOS": "boston-bruins",
    "BUF": "buffalo-sabres",
    "CGY": "calgary-flames",
    "CAR": "carolina-hurricanes",
    "CHI": "chicago-blackhawks",
    "COL": "colorado-avalanche",
    "CBJ": "columbus-blue-jackets",
    "DAL": "dallas-stars",
    "DET": "detroit-red-wings",
    "EDM": "edmonton-oilers",
    "FLA": "florida-panthers",
    "LAK": "los-angeles-kings",
    "MIN": "minnesota-wild",
    "MTL": "montreal-canadiens",
    "NSH": "nashville-predators",
    "NJD": "new-jersey-devils",
    "NYI": "new-york-islanders",
    "NYR": "new-york-rangers",
    "OTT": "ottawa-senators",
    "PHI": "philadelphia-flyers",
    "PIT": "pittsburgh-penguins",
    "SJS": "san-jose-sharks",
    "SEA": "seattle-kraken",
    "STL": "st-louis-blues",
    "TBL": "tampa-bay-lightning",
    "TOR": "toronto-maple-leafs",
    "UTA": "utah-hockey-club",
    "VAN": "vancouver-canucks",
    "VGK": "vegas-golden-knights",
    "WSH": "washington-capitals",
    "WPG": "winnipeg-jets",
}


def build_sportsbook_url(
    book_key: str,
    home_team: str = "",
    away_team: str = "",
    commence_time: str = "",
) -> str:
    """Build a sportsbook URL for an NHL game.

    Returns the NHL section URL for the given bookmaker. Falls back to
    empty string if the bookmaker is unknown.
    """
    return SPORTSBOOK_URLS.get(book_key, "")
