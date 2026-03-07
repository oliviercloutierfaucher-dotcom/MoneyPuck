# Phase 5: Injury Impact System - Research

**Researched:** 2026-03-07
**Domain:** NHL injury data integration, player impact tiering, win probability adjustment
**Confidence:** HIGH

## Summary

The injury impact system requires three capabilities: (1) fetching current NHL injury data, (2) classifying injured players by impact tier using TOI/points stats, and (3) applying win probability adjustments in the EdgeScoringAgent pipeline. The NHL's official `api-web.nhle.com` API does **not** have a dedicated injuries endpoint -- roster endpoints return only biographical data with no injury status fields. However, ESPN's undocumented public API at `site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries` provides structured injury data for all teams including player name, position, status (Out/Day-To-Day/IR), injury type, and projected return date. This endpoint is free, requires no authentication, and returns JSON.

For player tier classification, the NHL API's `/v1/club-stats/{team}/now` endpoint returns per-player season stats including `avgTimeOnIcePerGame`, `gamesPlayed`, `points`, `goals`, and `positionCode`. This provides everything needed to rank players by TOI within their positional group (forwards vs defensemen) and determine top-6 F / top-4 D classification.

**Primary recommendation:** Use ESPN injuries API as the primary injury data source, NHL club-stats API for player tier classification, and apply adjustments additively in `EdgeScoringAgent._estimate_win_probability()` alongside existing situational/goalie adjustments.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 3 tiers based on position and usage: Starting G (~3-5 pp), Top-6 F / Top-4 D (~1.5-2.5 pp), Bottom-6 F / Bottom-pair D (~0.5-1 pp)
- Tier classification uses NHL API player stats (TOI/GP, points) to auto-classify
- Multiple injuries compound: sum individual penalties, cap at ~8pp total adjustment
- Impact is symmetrical: if both teams equally depleted, adjustments cancel out
- Primary source: NHL API/structured data for injuries (ESPN API fulfills this — free, structured JSON)
- Injury statuses to track: IR, LTIR, Day-to-Day
- Refresh once per pipeline run, cache injury data per game day
- Game-time decisions (GTD): treat as 50% likely out, apply half the adjustment
- Manual overrides take priority over automated injury adjustments
- Automated injury adjustments apply AFTER manual overrides (additive, not replacing)
- Never auto-write to overrides.json
- Dashboard shows key injuries on game cards (top-tier only), total injury adjustment in tooltip
- Flag when injury data significantly affects model edge (>2pp swing)

### Claude's Discretion
- NHL API endpoint discovery for injury/roster data
- Exact TOI thresholds for tier classification
- How to handle mid-season trades (player moves team)
- Cache implementation details
- Test structure and synthetic injury scenarios
- Whether to add an --injuries CLI flag for standalone injury report

### Deferred Ideas (OUT OF SCOPE)
- Full WAR/GAR integration for precise player value
- Historical injury data for backtesting impact
- Injury trend analysis (frequently injured players)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R4.1 | Fetch daily injury reports from NHL API | ESPN injuries API provides structured JSON for all teams; NHL club-stats provides player TOI for tier classification |
| R4.2 | Tiered impact: top-6 F, top-4 D, starting G adjustments | NHL club-stats `/v1/club-stats/{team}/now` provides `avgTimeOnIcePerGame`, `positionCode`, `points` per player |
| R4.3 | Win probability adjustment based on missing player value | Additive adjustment in `_estimate_win_probability()` alongside `sit_adj` and `goalie_adj`; cap at 8pp |
| R4.4 | Manual override capability (existing overrides.json extended) | Existing `load_overrides()` and `apply_overrides()` remain unchanged; automated injuries layer separately |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| urllib.request | stdlib | HTTP requests to ESPN/NHL APIs | Already used throughout nhl_api.py; no new dependencies |
| json | stdlib | Parse API responses | Already used |
| functools.lru_cache | stdlib | Cache injury + player stats per day | Lightweight, no external deps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses | stdlib | InjuredPlayer, InjuryReport models | Consistent with TeamMetrics, ValueCandidate patterns |
| datetime | stdlib | Cache key generation, expiry checking | Already imported everywhere |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ESPN injuries API | BALLDONTLIE API | BALLDONTLIE requires API key + paid tier for production; ESPN is free and unauthenticated |
| ESPN injuries API | Scraping CBS/ESPN HTML | Fragile, slower, more code; ESPN JSON API is structured and reliable |
| NHL club-stats for TOI | MoneyPuck player data | MoneyPuck is team-level aggregates, not per-player; NHL API has individual player stats |

**Installation:**
```bash
# No new dependencies required — all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
app/
  data/
    injuries.py          # NEW: ESPN injury fetcher + NHL player stats fetcher
  core/
    injury_impact.py     # NEW: Tier classification + adjustment calculation
    agents.py            # MODIFY: Add injury_adj in EdgeScoringAgent
    service.py           # MODIFY: Fetch injuries in pipeline, pass to scoring
    models.py            # MODIFY: Add InjuredPlayer dataclass, injury fields to TeamMetrics
  web/
    presentation.py      # MODIFY: Show injuries on game cards
```

### Pattern 1: Data Fetcher (injuries.py)
**What:** Fetch injury data from ESPN API and player stats from NHL club-stats API. Follow existing `_fetch_json()` pattern from `nhl_api.py`.
**When to use:** Every pipeline run, cached per game day.
**Example:**
```python
# Source: ESPN undocumented API (verified 2026-03-07)
# GET https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries

from app.data.nhl_api import _fetch_json

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"

def fetch_injuries() -> list[dict]:
    """Fetch current NHL injuries from ESPN API.
    Returns list of {team_abbrev, player_name, position, status, injury_type, return_date}.
    """
    data = _fetch_json(ESPN_INJURIES_URL)
    injuries = []
    for team_entry in data.get("injuries", []):
        team_abbrev = team_entry.get("abbreviation", "")  # e.g. "TOR", "EDM"
        for inj in team_entry.get("injuries", []):
            athlete = inj.get("athlete", {})
            pos = athlete.get("position", {})
            details = inj.get("details", {})
            injuries.append({
                "team": team_abbrev,
                "player_name": athlete.get("displayName", ""),
                "position": pos.get("abbreviation", ""),  # C, LW, RW, D, G
                "status": inj.get("status", ""),  # "Out", "Day-To-Day", "Injured Reserve"
                "injury_type": details.get("type", ""),
                "return_date": details.get("returnDate", ""),
            })
    return injuries
```

### Pattern 2: Player Tier Classification (injury_impact.py)
**What:** Use NHL club-stats to rank players by TOI within their team and position group.
**When to use:** Once per day, cached alongside injury data.
**Example:**
```python
# Source: NHL API (verified 2026-03-07)
# GET https://api-web.nhle.com/v1/club-stats/{team}/now

def fetch_team_player_stats(team_code: str) -> list[dict]:
    """Fetch player stats for tier classification."""
    url = f"https://api-web.nhle.com/v1/club-stats/{team_code}/now"
    data = _fetch_json(url)
    players = []
    for skater in data.get("skaters", []):
        players.append({
            "player_id": skater.get("playerId"),
            "name": f"{skater['firstName']['default']} {skater['lastName']['default']}",
            "position": skater.get("positionCode", ""),  # C, L, R, D
            "toi_per_game": skater.get("avgTimeOnIcePerGame", 0),  # seconds
            "games_played": skater.get("gamesPlayed", 0),
            "points": skater.get("points", 0),
        })
    for goalie in data.get("goalies", []):
        players.append({
            "player_id": goalie.get("playerId"),
            "name": f"{goalie['firstName']['default']} {goalie['lastName']['default']}",
            "position": "G",
            "games_played": goalie.get("gamesPlayed", 0),
            "games_started": goalie.get("gamesStarted", 0),
        })
    return players

def classify_player_tier(player: dict, team_players: list[dict]) -> str:
    """Classify player into impact tier based on TOI rank within team."""
    pos = player["position"]
    if pos == "G":
        return "starting_g"  # Goalie handled by Phase 4 resolver

    # Forwards: C, L, R (or LW, RW from ESPN)
    is_forward = pos in ("C", "L", "R", "LW", "RW")
    is_defense = pos == "D"

    if is_forward:
        forwards = sorted(
            [p for p in team_players if p["position"] in ("C", "L", "R")],
            key=lambda p: p.get("toi_per_game", 0),
            reverse=True,
        )
        rank = next((i for i, p in enumerate(forwards) if p["player_id"] == player["player_id"]), len(forwards))
        return "top6_f" if rank < 6 else "bottom6_f"

    if is_defense:
        defensemen = sorted(
            [p for p in team_players if p["position"] == "D"],
            key=lambda p: p.get("toi_per_game", 0),
            reverse=True,
        )
        rank = next((i for i, p in enumerate(defensemen) if p["player_id"] == player["player_id"]), len(defensemen))
        return "top4_d" if rank < 4 else "bottom_d"

    return "bottom6_f"  # fallback
```

### Pattern 3: Adjustment Calculation
**What:** Sum per-player adjustments for each team, cap total, apply symmetrically.
**When to use:** During edge scoring for every game.
**Example:**
```python
TIER_IMPACT = {
    "starting_g": 4.0,    # pp midpoint of 3-5 range
    "top6_f": 2.0,         # pp midpoint of 1.5-2.5 range
    "top4_d": 1.5,         # pp midpoint of 1-2 range
    "bottom6_f": 0.75,     # pp midpoint of 0.5-1 range
    "bottom_d": 0.75,      # pp midpoint of 0.5-1 range
}
GTD_MULTIPLIER = 0.5  # Day-to-Day players get half impact
MAX_INJURY_ADJ = 8.0  # pp cap per team

def calculate_injury_adjustment(
    home_team: str, away_team: str, injuries: list[dict], player_tiers: dict
) -> float:
    """Calculate net injury adjustment from home team's perspective.
    Positive = home team has injury advantage (away more depleted).
    """
    def team_penalty(team: str) -> float:
        team_injuries = [i for i in injuries if i["team"] == team]
        total = 0.0
        for inj in team_injuries:
            tier = player_tiers.get((team, inj["player_name"]), "bottom6_f")
            impact = TIER_IMPACT.get(tier, 0.75)
            if inj["status"] == "Day-To-Day":
                impact *= GTD_MULTIPLIER
            total += impact
        return min(total, MAX_INJURY_ADJ)

    home_penalty = team_penalty(home_team)
    away_penalty = team_penalty(away_team)
    # Net adjustment: positive means home benefits (away more hurt)
    return (away_penalty - home_penalty) / 100.0  # convert pp to probability
```

### Pattern 4: Pipeline Integration
**What:** Add injury fetch to `build_market_snapshot()` thread pool, pass to EdgeScoringAgent.
**When to use:** Follow existing pattern of parallel data fetching.
**Example:**
```python
# In service.py build_market_snapshot():
# Add to ThreadPoolExecutor alongside odds, moneypuck, goalie, polymarket, df futures:
injury_future = pool.submit(fetch_injuries_safe)

# In EdgeScoringAgent.run():
# Add injury_adj alongside sit_adj and g_adj in _estimate_win_probability()
```

### Anti-Patterns to Avoid
- **Building a scraper for injury data:** ESPN provides structured JSON -- no HTML parsing needed.
- **Modifying overrides.json programmatically:** CONTEXT.md explicitly says never auto-write. Keep automated and manual cleanly separated.
- **Fetching per-player stats on every run:** Cache player stats per day -- TOI rankings barely change game-to-game.
- **Applying goalie injury adjustment AND Phase 4 goalie adjustment:** Phase 4 already handles goalie resolution. The injury system should detect goalie injuries to inform the dashboard display but should NOT double-apply goalie impact (Phase 4's resolver already switches to backup stats when starter is injured).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Injury data collection | Web scraper for CBS/ESPN HTML | ESPN JSON API endpoint | Structured, free, no auth, no parsing fragility |
| Player TOI ranking | Custom stats database | NHL club-stats API `/v1/club-stats/{team}/now` | Real-time, per-team, includes TOI/GP/points |
| Team abbreviation mapping | Hard-coded ESPN-to-NHL map | ESPN already uses standard NHL abbreviations (TOR, EDM, etc.) | Verified: ESPN `abbreviation` field matches NHL conventions |
| Cache invalidation | Custom TTL logic | Simple date-key cache (injuries change daily, not hourly) | `@lru_cache` with date key or dict keyed by date string |

**Key insight:** Both ESPN and NHL APIs return data in formats compatible with the existing project. ESPN team abbreviations match NHL conventions. No translation layer needed.

## Common Pitfalls

### Pitfall 1: Double-Counting Goalie Injuries
**What goes wrong:** Phase 4 already resolves the starting goalie (using DailyFaceoff + fallback). If the injury system also applies a 3-5pp goalie penalty, the goalie impact is counted twice.
**Why it happens:** Phase 4 switches to the backup goalie's save%/GAA when the starter is confirmed out. The goalie_matchup_adjustment already reflects the weaker backup.
**How to avoid:** Skip goalie injuries in the automated adjustment calculation. Only apply forward/defenseman injury penalties. Use goalie injuries for dashboard display only.
**Warning signs:** Model probability shifts >5pp for a single goalie injury when Phase 4 is active.

### Pitfall 2: ESPN Abbreviation Mismatches
**What goes wrong:** ESPN may use different abbreviations for some teams than the NHL API or the Odds API.
**Why it happens:** Historical team codes vary across providers (e.g., "PHX" vs "ARI" vs "UTA").
**How to avoid:** Build a small normalization map for known differences. Test with all 32 teams. Currently the most likely mismatch is Utah (UTA vs UTAH).
**Warning signs:** Injuries found for a team code that doesn't match any team in `team_strength`.

### Pitfall 3: Stale Player Stats for Tier Classification
**What goes wrong:** Fetching player stats for all 32 teams on every pipeline run creates 32 API calls, potentially slow and rate-limited.
**Why it happens:** TOI rankings are needed per-team to classify injured players.
**How to avoid:** Cache player stats for 24 hours (TOI rankings are very stable day-to-day). Fetch stats lazily -- only for teams with active injuries.
**Warning signs:** Pipeline run time increases >15s from player stats fetching.

### Pitfall 4: Name Matching Between ESPN Injuries and NHL Player Stats
**What goes wrong:** ESPN uses display names ("Connor McDavid") while NHL API uses separate firstName/lastName objects. Accented characters, suffixes (Jr., III), and nicknames can cause mismatches.
**Why it happens:** Two different data sources with different name conventions.
**How to avoid:** Match by last name + team code (same pattern as Phase 4 goalie resolver). Fall back to fuzzy matching only if exact match fails.
**Warning signs:** Injured players not found in team player stats lookup.

### Pitfall 5: Overriding Manual Overrides
**What goes wrong:** Automated injury adjustment conflicts with a manually set `strength_penalty` in overrides.json.
**Why it happens:** Both systems adjust the same team strength.
**How to avoid:** CONTEXT.md is clear: manual overrides win on conflicts. Apply injury adjustments in EdgeScoringAgent as a separate `injury_adj` parameter, after `apply_overrides()` has already run.
**Warning signs:** Same team has both manual override AND automated injury adjustment that are redundant.

## Code Examples

### Integration Point: EdgeScoringAgent._estimate_win_probability()
```python
# Current signature (agents.py line ~569):
@staticmethod
def _estimate_win_probability(
    home_team, away_team, strength, sit_adj=0.0, goalie_adj=0.0,
    home_advantage=0.14, logistic_k=0.9, elo_tracker=None, elo_weight=0.25,
) -> tuple[float, float, float]:

# Add injury_adj parameter:
@staticmethod
def _estimate_win_probability(
    home_team, away_team, strength, sit_adj=0.0, goalie_adj=0.0,
    injury_adj=0.0,  # NEW: net injury impact in probability units
    home_advantage=0.14, logistic_k=0.9, elo_tracker=None, elo_weight=0.25,
) -> tuple[float, float, float]:
    # ... existing logic ...
    # Line ~616: Add injury_adj to total
    total_adj = sit_adj + goalie_adj / 100.0 + momentum_adj + injury_adj
```

### Integration Point: build_market_snapshot() parallel fetch
```python
# In service.py, add to ThreadPoolExecutor (line ~58):
with ThreadPoolExecutor(max_workers=6) as pool:  # was 5
    odds_future = pool.submit(market_agent.run, config)
    moneypuck_future = pool.submit(data_agent.run, config)
    goalie_future = pool.submit(_fetch_goalies_safe)
    polymarket_future = pool.submit(fetch_polymarket_odds)
    df_future = pool.submit(_fetch_df_starters_safe)
    injury_future = pool.submit(_fetch_injuries_safe)  # NEW
```

### ESPN Position Code Mapping
```python
# ESPN position abbreviations to project tier groups:
FORWARD_POSITIONS = {"C", "LW", "RW", "L", "R", "F"}
DEFENSE_POSITIONS = {"D"}
GOALIE_POSITIONS = {"G"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No injury awareness | Manual overrides.json | Phase 1 | User must manually set strength_penalty |
| GP-leader goalie heuristic | DailyFaceoff confirmed starters | Phase 4 | Goalie injuries partially handled |
| No per-player stats | NHL club-stats API per-team | Available now | Enables automated TOI-based tier classification |

**Deprecated/outdated:**
- Old NHL API (statsapi.web.nhl.com) was deprecated in 2023 -- project correctly uses api-web.nhle.com/v1
- NHL roster endpoint (`/v1/roster/{team}/current`) does NOT include injury data -- confirmed via testing

## Open Questions

1. **ESPN team abbreviation edge cases**
   - What we know: ESPN uses standard abbreviations (TOR, EDM, BOS, etc.) that match NHL API
   - What's unclear: Whether newer teams like UTA (Utah Hockey Club) use exactly the same code
   - Recommendation: Build a small normalization map, test with all 32 teams on first implementation

2. **ESPN API stability / rate limiting**
   - What we know: Endpoint is public, unauthenticated, returns full league injury data in one call
   - What's unclear: Whether ESPN rate-limits or blocks frequent callers
   - Recommendation: Cache aggressively (one call per pipeline run, ~1 call per hour max). Add resilient fallback pattern like existing `_fetch_json()`.

3. **Goalie injury interaction with Phase 4**
   - What we know: Phase 4 resolves confirmed starters and uses their actual save%/GAA
   - What's unclear: Whether Phase 4 already correctly handles IR/LTIR goalies (DailyFaceoff should show backup as starter)
   - Recommendation: Do NOT apply automated goalie injury penalty. Phase 4 handles this. Use goalie injuries for display only.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini or pyproject.toml (existing) |
| Quick run command | `pytest tests/data/test_injuries.py tests/core/test_injury_impact.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R4.1 | ESPN injury API fetch + parsing | unit | `pytest tests/data/test_injuries.py::test_fetch_injuries -x` | Wave 0 |
| R4.1 | NHL club-stats fetch + parsing | unit | `pytest tests/data/test_injuries.py::test_fetch_player_stats -x` | Wave 0 |
| R4.2 | Tier classification by TOI rank | unit | `pytest tests/core/test_injury_impact.py::test_tier_classification -x` | Wave 0 |
| R4.2 | GTD half-impact applied correctly | unit | `pytest tests/core/test_injury_impact.py::test_gtd_half_impact -x` | Wave 0 |
| R4.3 | Net adjustment calculation + 8pp cap | unit | `pytest tests/core/test_injury_impact.py::test_adjustment_cap -x` | Wave 0 |
| R4.3 | Symmetrical cancellation | unit | `pytest tests/core/test_injury_impact.py::test_symmetrical -x` | Wave 0 |
| R4.3 | Integration in EdgeScoringAgent | integration | `pytest tests/core/test_agents.py::test_injury_adj -x` | Wave 0 |
| R4.4 | Manual override priority over automated | integration | `pytest tests/core/test_injury_impact.py::test_override_priority -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/data/test_injuries.py tests/core/test_injury_impact.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/data/test_injuries.py` -- covers R4.1 (ESPN + NHL API fetch/parse)
- [ ] `tests/core/test_injury_impact.py` -- covers R4.2, R4.3, R4.4 (tiers, adjustments, overrides)
- [ ] Synthetic ESPN injury response fixtures for deterministic testing

## Sources

### Primary (HIGH confidence)
- ESPN NHL Injuries API: `https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries` -- verified live, returns structured JSON with team abbreviations, player positions, status, return dates
- NHL Club Stats API: `https://api-web.nhle.com/v1/club-stats/{team}/now` -- verified live, returns per-player TOI, GP, points, position
- NHL Roster API: `https://api-web.nhle.com/v1/roster/{team}/current` -- verified: does NOT include injury status fields

### Secondary (MEDIUM confidence)
- [Zmalski/NHL-API-Reference](https://github.com/Zmalski/NHL-API-Reference) -- unofficial but comprehensive NHL API documentation
- [ESPN hidden API docs](https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b) -- community-documented ESPN endpoints

### Tertiary (LOW confidence)
- ESPN API rate limits/stability -- no official documentation; anecdotal evidence suggests lenient limits for low-frequency usage

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, no new dependencies, follows existing patterns
- Architecture: HIGH -- clear integration points identified in existing codebase (agents.py, service.py)
- Pitfalls: HIGH -- goalie double-counting identified as critical risk; name matching well-understood from Phase 4
- Data sources: MEDIUM -- ESPN API is undocumented/unofficial; stable but could change without notice

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (ESPN API endpoint stability; 30 days for stable domain)
