# Phase 4: Starting Goalies - Research

**Researched:** 2026-03-07
**Domain:** NHL goalie data fetching, pipeline integration, model accuracy validation
**Confidence:** HIGH

## Summary

This phase replaces the GP-leader heuristic (`infer_likely_starter()`) with confirmed starting goalie data from DailyFaceoff (primary pre-game source) and the NHL API gamecenter endpoint (post-game verification). Live investigation of the NHL API confirms that the `/v1/gamecenter/{id}/landing` endpoint provides goalie comparison data (both team goalies with season stats) but does NOT include a pre-game "confirmed starter" indicator. The `/v1/gamecenter/{id}/boxscore` endpoint includes a `starter: true/false` boolean on each goalie entry, but only for games that have started or completed.

DailyFaceoff is the definitive pre-game source. Their starting goalies page (`/starting-goalies/{YYYY-MM-DD}`) embeds complete matchup data as JSON in a `__NEXT_DATA__` script tag, including goalie names, team identifiers, season stats, and critically a confirmation status field (`newsStrengthId`: 2=Confirmed, 3=Likely, null=Unconfirmed). This eliminates the need for HTML scraping -- the data can be extracted by parsing the embedded JSON.

**Primary recommendation:** Implement a 3-tier goalie resolution: (1) DailyFaceoff JSON scrape for pre-game confirmations, (2) NHL API gamecenter/landing goalieComparison for enrichment stats, (3) existing `infer_likely_starter()` as fallback. No new dependencies required -- stdlib `urllib` + `json` + `html.parser` or regex extraction suffice.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Primary source: NHL API `/gamecenter/{gameId}/landing` endpoint -- free, no scraping, includes confirmed starters ~1-2 hours before puck drop
- Secondary fallback: DailyFaceoff confirmed starters page (scrape) -- available earlier in the day (by ~noon ET)
- Try NHL API first; if starter not yet confirmed, try DailyFaceoff; if neither available, fall back to GP-leader heuristic
- No paid data feeds -- keep it free
- Cache confirmed starter data per game day (don't re-fetch within same pipeline run)
- 3-tier fallback: confirmed starter -> DailyFaceoff -> GP-leader heuristic
- When using GP-leader fallback, flag the prediction as "unconfirmed starter" in output
- Never skip the goalie adjustment entirely -- GP-leader is better than nothing
- Historical confirmed starter data is NOT available for past seasons -- can't backtest with real confirmations
- Validate by simulating: compare model output with correct starter vs wrong starter on known backup-start games
- Use 2024-25 season games where backup started to measure GP-leader heuristic error
- Success: demonstrate correct goalie identification improves Brier score by >0.005 on those games
- COVID season excluded from validation

### Claude's Discretion
- NHL API endpoint discovery and parsing details
- DailyFaceoff scraping implementation (CSS selectors, etc.)
- Caching strategy (in-memory dict with TTL vs file-based)
- How to identify backup-start games in historical data for validation
- Whether to add GSAx alongside save% or just improve save% accuracy
- Test structure and synthetic data design

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R3.1 | Fetch confirmed starters from DailyFaceoff or NHL API | DailyFaceoff `__NEXT_DATA__` JSON provides goalie name + confirmation status; NHL API gamecenter/landing provides goalie comparison but NO pregame confirmation flag |
| R3.2 | Use confirmed goalie's actual save%/GSAx instead of GP-leader's | NHL API goalieSeasonStats provides per-goalie savePctg, GAA, GP, wins; DailyFaceoff also includes save%, GAA |
| R3.3 | Graceful fallback to GP-leader when no confirmation available | Existing `infer_likely_starter()` preserved as tier-3 fallback; confirmation status field enables fallback logic |
| R3.4 | Timing: data available by early afternoon on game days | DailyFaceoff updates by ~noon ET; NHL API has no pregame confirmation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| urllib.request | stdlib | HTTP requests to DailyFaceoff and NHL API | Already used in `nhl_api.py`, no new deps |
| json | stdlib | Parse NHL API responses and DailyFaceoff `__NEXT_DATA__` | Already used throughout |
| html.parser / re | stdlib | Extract `__NEXT_DATA__` JSON from DailyFaceoff HTML | Lightweight, no BeautifulSoup dependency needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Mock HTTP responses in tests | All goalie fetcher tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib urllib | requests/httpx | Would add dependency; project consistently uses urllib |
| regex JSON extract | BeautifulSoup | Overkill for extracting one script tag; adds dependency |

**Installation:**
```bash
# No new dependencies required
```

## Architecture Patterns

### Recommended Project Structure
```
app/
  data/
    nhl_api.py          # Add: fetch_confirmed_starter() using gamecenter landing
    dailyfaceoff.py     # NEW: DailyFaceoff scraper for pre-game confirmations
  core/
    agents.py           # Modify: TeamStrengthAgent uses confirmed starter
    service.py          # Modify: fetch confirmed starters in parallel
    models.py           # Modify: add starter_confirmed flag to TeamMetrics (or ValueCandidate)
```

### Pattern 1: DailyFaceoff JSON Extraction
**What:** Parse embedded `__NEXT_DATA__` JSON from DailyFaceoff HTML instead of scraping DOM.
**When to use:** Every pre-game goalie confirmation fetch.
**Example:**
```python
# Source: Live investigation of https://www.dailyfaceoff.com/starting-goalies/2026-03-07
import json
import re
from urllib.request import Request, urlopen

def fetch_dailyfaceoff_starters(date_str: str) -> list[dict]:
    """Fetch confirmed starters from DailyFaceoff for a given date.

    Returns list of dicts with keys:
        home_team_slug, away_team_slug,
        home_goalie_name, away_goalie_name,
        home_status (Confirmed/Likely/None), away_status,
        home_save_pct, away_save_pct, etc.
    """
    url = f"https://www.dailyfaceoff.com/starting-goalies/{date_str}"
    req = Request(url, headers={"User-Agent": "MoneyPuck/1.0"})
    html = urlopen(req, timeout=15).read().decode("utf-8")

    # Extract __NEXT_DATA__ JSON
    match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return []

    data = json.loads(match.group(1))
    games = data.get("props", {}).get("pageProps", {}).get("data", [])

    starters = []
    for game in games:
        starters.append({
            "home_goalie": game.get("homeGoalieName"),
            "away_goalie": game.get("awayGoalieName"),
            "home_status": _status_label(game.get("homeNewsStrengthName")),
            "away_status": _status_label(game.get("awayNewsStrengthName")),
            "home_save_pct": game.get("homeGoalieSavePercentage"),
            "away_save_pct": game.get("awayGoalieSavePercentage"),
            "home_team_slug": game.get("homeTeamSlug"),
            "away_team_slug": game.get("awayTeamSlug"),
        })
    return starters

def _status_label(strength_name: str | None) -> str:
    if strength_name == "Confirmed":
        return "confirmed"
    elif strength_name == "Likely":
        return "likely"
    return "unconfirmed"
```

### Pattern 2: NHL API Gamecenter Goalie Enrichment
**What:** Use `/v1/gamecenter/{id}/landing` matchup.goalieComparison for per-goalie season stats.
**When to use:** When we need accurate save%/GAA for a specific goalie (not just the GP leader).
**Example:**
```python
# Source: Live API investigation of https://api-web.nhle.com/v1/gamecenter/2025020990/landing
# Response structure (verified 2026-03-07):
# data["matchup"]["goalieComparison"]["homeTeam"]["leaders"] = [
#   {"playerId": 8480280, "name": {"default": "J. Swayman"},
#    "gamesPlayed": 40, "savePctg": 0.905, "gaa": 2.85, ...},
#   {"playerId": 8476914, "name": {"default": "J. Korpisalo"},
#    "gamesPlayed": 24, "savePctg": 0.893, "gaa": 3.20, ...}
# ]
# data["matchup"]["goalieSeasonStats"]["goalies"] = [
#   {"playerId": ..., "savePctg": 0.905, "goalsAgainstAvg": 2.85,
#    "gamesPlayed": 40, "wins": 23, "saves": 1058, "shotsAgainst": 1169, ...}
# ]

def fetch_game_goalies(game_id: int) -> dict:
    """Fetch goalie data for a specific game from NHL API.

    Returns dict keyed by team abbrev, each containing list of goalies
    with their season stats (savePctg, gaa, gamesPlayed).
    """
    data = _fetch_json(f"{NHL_API_BASE}/gamecenter/{game_id}/landing")
    matchup = data.get("matchup", {})
    comparison = matchup.get("goalieComparison", {})

    result = {}
    for side, key in [("homeTeam", "home_team"), ("awayTeam", "away_team")]:
        team_abbrev = data.get(side, {}).get("abbrev", "")
        leaders = comparison.get(side, {}).get("leaders", [])
        result[team_abbrev] = [
            {
                "player_id": g.get("playerId"),
                "name": g.get("name", {}).get("default", ""),
                "games_played": g.get("gamesPlayed", 0),
                "save_pct": g.get("savePctg", 0.0),
                "gaa": g.get("gaa", 0.0),
            }
            for g in leaders
        ]
    return result
```

### Pattern 3: 3-Tier Goalie Resolution
**What:** Try DailyFaceoff confirmed -> NHL API goalie list -> GP-leader fallback.
**When to use:** In `TeamStrengthAgent.run()` or `build_market_snapshot()`.
**Example:**
```python
def resolve_starter(team_code: str, game_id: int, df_starters: dict,
                    goalie_stats: list) -> tuple[dict, str]:
    """Resolve starting goalie with 3-tier fallback.

    Returns (goalie_dict, source) where source is one of:
        "confirmed", "likely", "gp_leader"
    """
    # Tier 1: DailyFaceoff confirmation
    df_entry = df_starters.get(team_code)
    if df_entry and df_entry["status"] in ("confirmed", "likely"):
        # Match goalie name to season stats for accurate save%
        return _match_goalie_to_stats(df_entry["name"], goalie_stats, team_code), df_entry["status"]

    # Tier 2 is implicitly handled by tier 1 (DailyFaceoff IS the confirmation source)
    # NHL API gamecenter doesn't have confirmation, just goalie list

    # Tier 3: GP-leader heuristic (existing)
    starter = infer_likely_starter(team_code, goalie_stats)
    return starter, "gp_leader"
```

### Anti-Patterns to Avoid
- **Scraping DailyFaceoff HTML DOM:** The page is React/Next.js -- DOM structure changes frequently. Extract `__NEXT_DATA__` JSON instead, which is the stable data contract.
- **Relying on NHL API for pregame confirmation:** Live testing confirms the NHL API does NOT provide a "confirmed starter" flag before puck drop. `playerByGameStats` is empty for future games. Only use NHL API for enrichment stats.
- **Blocking pipeline on goalie fetch:** If DailyFaceoff is slow or down, the pipeline must not hang. Use timeout + fallback.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Team code mapping (DailyFaceoff slugs -> NHL abbrevs) | Complex alias table | Simple slug-to-abbrev dict | DailyFaceoff uses slugs like "boston-bruins"; need mapping to "BOS" |
| Goalie name matching | Fuzzy matching | Exact match on player name from goalie_stats | Names from DailyFaceoff match NHL API format closely enough |
| HTML parsing | Full DOM parser | Regex for `__NEXT_DATA__` extraction | Single script tag extraction; BeautifulSoup is overkill |
| Rate limiting | Custom rate limiter | Simple per-run caching (one fetch per pipeline run) | Only fetching once per run; no need for complex rate limiting |

**Key insight:** The DailyFaceoff `__NEXT_DATA__` JSON is the single most valuable data source. It provides everything needed: goalie name, confirmation status, and basic stats. The NHL API gamecenter endpoint is useful for per-goalie season stats enrichment but cannot tell us WHO starts.

## Common Pitfalls

### Pitfall 1: DailyFaceoff Slug-to-Team-Code Mapping
**What goes wrong:** DailyFaceoff uses team slugs like "toronto-maple-leafs" while the model uses NHL abbreviations like "TOR".
**Why it happens:** Different data sources use different identifiers.
**How to avoid:** Build a static `SLUG_TO_ABBREV` mapping dict (32 teams). This is stable -- teams don't change slugs mid-season.
**Warning signs:** Goalie confirmations not matching any team in the pipeline output.

### Pitfall 2: DailyFaceoff Page Structure Changes
**What goes wrong:** The `__NEXT_DATA__` JSON key names change when DailyFaceoff updates their site.
**Why it happens:** We're relying on an undocumented data format from a third-party site.
**How to avoid:** (1) Defensive key access with `.get()` everywhere, (2) graceful fallback to GP-leader if parsing fails, (3) log warnings on unexpected structure.
**Warning signs:** All goalies suddenly "unconfirmed" despite it being game day afternoon.

### Pitfall 3: Timing Window
**What goes wrong:** Pipeline runs before DailyFaceoff has confirmations, always falls back to GP-leader.
**Why it happens:** Confirmations typically appear by noon ET but the pipeline might run at 8 AM.
**How to avoid:** Accept "likely" status as good enough (newsStrengthId=3), not just "confirmed" (newsStrengthId=2). Log the confirmation source so users can see when data improves.
**Warning signs:** `starter_source: "gp_leader"` on every game despite confirmations being available later.

### Pitfall 4: Goalie Name Mismatch Between Sources
**What goes wrong:** DailyFaceoff says "J. Swayman" but goalie_stats has "Jeremy Swayman" -- can't match.
**Why it happens:** DailyFaceoff uses full names, NHL API leaders use abbreviated first names.
**How to avoid:** Match on team_code + last_name as primary key (very few teams have two goalies with same last name). Fall back to full name match. Player ID match is ideal if DailyFaceoff provides IDs.
**Warning signs:** Confirmed goalie found but can't look up their save%.

### Pitfall 5: Validation Methodology
**What goes wrong:** Can't prove Brier improvement because historical confirmed starters aren't available.
**Why it happens:** DailyFaceoff doesn't serve historical data; NHL API boxscores only have starters for completed games.
**How to avoid:** Use NHL API boxscores to identify backup-start games retroactively (the goalie with `starter: true` and fewer GP is the backup). Then simulate: what was the GP-leader's save% vs the actual starter's save%? Measure the error.
**Warning signs:** Comparing wrong things -- need to measure probability error, not just save% error.

## Code Examples

### DailyFaceoff Team Slug Mapping
```python
# Source: DailyFaceoff page structure (verified 2026-03-07)
SLUG_TO_ABBREV = {
    "anaheim-ducks": "ANA", "boston-bruins": "BOS", "buffalo-sabres": "BUF",
    "calgary-flames": "CGY", "carolina-hurricanes": "CAR", "chicago-blackhawks": "CHI",
    "colorado-avalanche": "COL", "columbus-blue-jackets": "CBJ", "dallas-stars": "DAL",
    "detroit-red-wings": "DET", "edmonton-oilers": "EDM", "florida-panthers": "FLA",
    "los-angeles-kings": "LAK", "minnesota-wild": "MIN", "montreal-canadiens": "MTL",
    "nashville-predators": "NSH", "new-jersey-devils": "NJD", "new-york-islanders": "NYI",
    "new-york-rangers": "NYR", "ottawa-senators": "OTT", "philadelphia-flyers": "PHI",
    "pittsburgh-penguins": "PIT", "san-jose-sharks": "SJS", "seattle-kraken": "SEA",
    "st-louis-blues": "STL", "tampa-bay-lightning": "TBL", "toronto-maple-leafs": "TOR",
    "utah-hockey-club": "UTA", "vancouver-canucks": "VAN", "vegas-golden-knights": "VGK",
    "washington-capitals": "WSH", "winnipeg-jets": "WPG",
}
```

### Identifying Backup Starts from Historical Boxscores
```python
# Source: Live API investigation of boxscore endpoint (verified 2026-03-07)
# boxscore.playerByGameStats.homeTeam.goalies[].starter = true/false
# The goalie with starter=True who has FEWER season GP than the team's GP leader
# is a backup start.

def identify_backup_starts(game_ids: list[int], goalie_stats: list[dict]) -> list[dict]:
    """Find games where a backup goalie started (for validation).

    Uses NHL API boxscores to find the actual starter, then compares
    against who infer_likely_starter() would have picked.
    """
    backup_starts = []
    for gid in game_ids:
        boxscore = _fetch_json(f"{NHL_API_BASE}/gamecenter/{gid}/boxscore")
        pbgs = boxscore.get("playerByGameStats", {})

        for side in ["homeTeam", "awayTeam"]:
            team_data = pbgs.get(side, {})
            team_abbrev = boxscore.get(side, {}).get("abbrev", "")
            goalies = team_data.get("goalies", [])

            actual_starter = next((g for g in goalies if g.get("starter")), None)
            if not actual_starter:
                continue

            # Who would GP-leader heuristic pick?
            gp_leader = infer_likely_starter(team_abbrev, goalie_stats)
            if gp_leader and actual_starter["name"]["default"] != gp_leader["player_name"]:
                backup_starts.append({
                    "game_id": gid,
                    "team": team_abbrev,
                    "actual_starter": actual_starter["name"]["default"],
                    "heuristic_pick": gp_leader["player_name"],
                })
    return backup_starts
```

### Integration Point: Modified TeamStrengthAgent
```python
# Source: Existing code at app/core/agents.py:188-194
# Current:
#   for team in teams:
#       starter = infer_likely_starter(team, goalie_stats)
#       if starter:
#           goalie_lookup[team] = starter

# New (conceptual):
#   confirmed_starters = fetch_confirmed_starters(schedule_date)  # DailyFaceoff
#   for team in teams:
#       starter, source = resolve_starter(team, confirmed_starters, goalie_stats)
#       if starter:
#           goalie_lookup[team] = starter
#           goalie_lookup[team]["source"] = source  # "confirmed"/"likely"/"gp_leader"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GP-leader heuristic | Confirmed starter feeds | Always available | ~25% of games had wrong goalie; 1-3pp probability error on those games |
| DOM scraping DailyFaceoff | `__NEXT_DATA__` JSON extraction | Next.js migration ~2023 | More stable, less breakage from CSS changes |
| Single goalie source | Multi-source with fallback | Best practice | Resilience against any single source going down |

**Key finding from CONTEXT.md:** The existing code documents this as a known limitation at `nhl_api.py:234-236`, with the exact improvement path we're implementing.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no config file, uses defaults) |
| Config file | none (discovery via `tests/` directory convention) |
| Quick run command | `python -m pytest tests/data/test_nhl_api.py tests/data/test_dailyfaceoff.py -x -q` |
| Full suite command | `python -m pytest -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R3.1 | DailyFaceoff scraper returns goalie + status | unit | `python -m pytest tests/data/test_dailyfaceoff.py -x` | Wave 0 |
| R3.1 | NHL API gamecenter goalie enrichment | unit | `python -m pytest tests/data/test_nhl_api.py -x` | Extend existing |
| R3.2 | Confirmed goalie's actual save% used | unit | `python -m pytest tests/core/test_agents.py -x -k goalie` | Wave 0 |
| R3.3 | 3-tier fallback (confirmed -> likely -> GP-leader) | unit | `python -m pytest tests/data/test_dailyfaceoff.py -x -k fallback` | Wave 0 |
| R3.3 | DailyFaceoff down -> GP-leader used | unit | `python -m pytest tests/data/test_dailyfaceoff.py -x -k failure` | Wave 0 |
| R3.4 | Confirmation status labeled in output | unit | `python -m pytest tests/core/test_agents.py -x -k starter_source` | Wave 0 |
| R3-val | Backup start identification from boxscores | unit | `python -m pytest tests/data/test_nhl_api.py -x -k backup` | Wave 0 |
| R3-val | Brier improvement on backup-start games | integration | `python -m pytest tests/core/test_validation.py -x -k goalie_brier` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/data/test_dailyfaceoff.py tests/data/test_nhl_api.py tests/core/test_agents.py -x -q`
- **Per wave merge:** `python -m pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/data/test_dailyfaceoff.py` -- covers R3.1, R3.3 (DailyFaceoff scraper)
- [ ] Tests for `fetch_game_goalies()` in `test_nhl_api.py` -- covers R3.1, R3.2
- [ ] Tests for `resolve_starter()` 3-tier fallback -- covers R3.3
- [ ] Tests for backup start identification from boxscores -- covers validation
- [ ] Tests for starter_source flag propagation -- covers R3.4

## Open Questions

1. **DailyFaceoff field names**
   - What we know: Page uses `__NEXT_DATA__` with fields like `homeGoalieName`, `homeNewsStrengthName`
   - What's unclear: Exact field names may vary; need to verify with a live fetch during implementation
   - Recommendation: First task should be a DailyFaceoff scraper with defensive `.get()` access and logging of unexpected structures

2. **GSAx availability**
   - What we know: NHL API provides save%, GAA, wins, games_played for each goalie
   - What's unclear: GSAx (Goals Saved Above Expected) is not in the NHL public API; it's a derived metric from MoneyPuck or other analytics sites
   - Recommendation: Start with save% (already in pipeline). GSAx could be computed from MoneyPuck CSV data if available per-goalie, but this is lower priority than getting the right goalie identified.

3. **Rate of backup starts in 2024-25**
   - What we know: CONTEXT.md says ~25% wrong goalie picks with GP-leader heuristic
   - What's unclear: Exact number of backup-start games in the validation season
   - Recommendation: First validation task should enumerate backup starts via boxscore API to size the impact

## Sources

### Primary (HIGH confidence)
- NHL API `api-web.nhle.com` - Live tested gamecenter/landing, gamecenter/boxscore, goalie-stats-leaders endpoints (2026-03-07)
- Existing codebase: `app/data/nhl_api.py`, `app/core/agents.py`, `app/core/service.py`, `app/math/math_utils.py`

### Secondary (MEDIUM confidence)
- [DailyFaceoff starting goalies page](https://www.dailyfaceoff.com/starting-goalies) - `__NEXT_DATA__` JSON structure verified via WebFetch
- [NHL API Reference (unofficial)](https://github.com/Zmalski/NHL-API-Reference) - Endpoint documentation
- [nhl-api-py](https://github.com/coreyjs/nhl-api-py) - Python client showing endpoint patterns

### Tertiary (LOW confidence)
- DailyFaceoff field name specifics (`homeNewsStrengthName` vs `homeNewsStrengthId`) -- need live verification during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; extending existing patterns
- Architecture: HIGH - Codebase already has the integration points documented; goalie_matchup_adjustment() needs no changes
- Pitfalls: HIGH - Live API testing revealed the key insight (NHL API has no pregame confirmation)
- DailyFaceoff parsing: MEDIUM - `__NEXT_DATA__` structure confirmed via WebFetch but exact field names need live verification
- Validation methodology: MEDIUM - Boxscore `starter` field confirmed; but actual backup-start rate and Brier impact untested

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable -- NHL API and DailyFaceoff patterns are season-stable)
