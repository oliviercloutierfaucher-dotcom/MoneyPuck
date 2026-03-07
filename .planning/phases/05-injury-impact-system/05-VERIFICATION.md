---
phase: 05-injury-impact-system
verified: 2026-03-07T23:45:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
---

# Phase 5: Injury Impact System Verification Report

**Phase Goal:** Automatically fetch daily NHL injury reports, classify missing players by impact tier, and adjust win probabilities accordingly.
**Verified:** 2026-03-07T23:45:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ESPN injuries API returns structured injury data for all 32 NHL teams | VERIFIED | `app/data/injuries.py:47-100` -- `fetch_injuries()` parses ESPN nested JSON, normalizes teams/positions, returns list of dicts. 11 tests in `tests/data/test_injuries.py`. |
| 2 | NHL club-stats API returns per-player TOI for tier classification | VERIFIED | `app/data/injuries.py:103-156` -- `fetch_team_player_stats()` parses skaters and goalies, extracts `avgTimeOnIcePerGame`, position, name. |
| 3 | Injured players are classified into correct tiers (starting_g, top6_f, top4_d, bottom6_f, bottom_d) | VERIFIED | `app/core/injury_impact.py:62-119` -- `classify_player_tier()` ranks by TOI within positional group. 22 tests in `tests/core/test_injury_impact.py`. |
| 4 | GTD players receive half the adjustment of confirmed-out players | VERIFIED | `app/core/injury_impact.py:238-239` -- checks for "Day-To-Day" or "DTD" in status, multiplies by `GTD_MULTIPLIER = 0.5`. |
| 5 | Multiple injuries compound with an 8pp cap per team | VERIFIED | `app/core/injury_impact.py:257-262` -- `MAX_INJURY_ADJ = 8.0`, logged and capped. |
| 6 | Net adjustment is symmetrical (both teams equally depleted cancels out) | VERIFIED | `app/core/injury_impact.py:266-270` -- `net_adj = (away_penalty - home_penalty) / 100.0`. |
| 7 | Goalie injuries are detected for display but NOT applied as adjustments | VERIFIED | `app/core/injury_impact.py:251-253` -- `if tier == "starting_g": continue` skips goalie in penalty sum, but goalie still appended to `injured_players` list for display. |
| 8 | Pipeline fetches injuries in parallel alongside odds, MoneyPuck, goalies, and DailyFaceoff | VERIFIED | `app/core/service.py:75` -- `injury_future = pool.submit(_fetch_injuries_safe)` as 6th worker in ThreadPoolExecutor. |
| 9 | EdgeScoringAgent applies injury_adj alongside sit_adj and goalie_adj | VERIFIED | `app/core/agents.py:575` -- `injury_adj: float = 0.0` parameter. Line 618: `total_adj = sit_adj + goalie_adj / 100.0 + momentum_adj + injury_adj`. |
| 10 | Manual overrides take priority -- injury adjustments layer separately AFTER apply_overrides() | VERIFIED | `app/core/service.py:380-420` -- `apply_overrides()` runs at line 380, injury tiers built at line 408-412, both passed to edge agent separately. |
| 11 | Dashboard game cards show key injured players (top-tier only) below team names | VERIFIED | `app/web/presentation.py:1540-1566` -- `renderInjurySection(g)` renders home/away key injuries. Called at line 1706 inside card template. |
| 12 | Dashboard flags games where injury adjustment causes >2pp swing | VERIFIED | `app/web/web_preview.py:660-686` -- `game_injury_data` includes `significant` flag. Presentation line 1561-1562 renders `adj_pp + "pp swing"` badge when significant. |
| 13 | Model correctly adjusts probability when key players are out | VERIFIED | `app/core/agents.py:664-677` -- `calculate_injury_adjustment()` called per game, result passed as `injury_adj` to `_estimate_win_probability()`. 3 integration tests in `tests/core/test_agents.py`. |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/data/injuries.py` | ESPN injury fetcher + NHL club-stats player stats fetcher | VERIFIED | 157 lines, exports `fetch_injuries`, `fetch_team_player_stats`. Substantive with full API parsing logic. |
| `app/core/injury_impact.py` | Tier classification + adjustment calculation | VERIFIED | 273 lines, exports `classify_player_tier`, `calculate_injury_adjustment`, `build_player_tiers`, `InjuredPlayer`, `TIER_IMPACT`. Complete implementation. |
| `tests/data/test_injuries.py` | Unit tests for injury data fetching | VERIFIED | 272 lines, 11 tests covering parsing, normalization, error handling. |
| `tests/core/test_injury_impact.py` | Unit tests for tier classification + adjustment math | VERIFIED | 346 lines, 22 tests covering all tiers, GTD, cap, symmetry, goalie exclusion. |
| `app/core/agents.py` | EdgeScoringAgent with injury_adj parameter | VERIFIED | `injury_adj` parameter at line 575, used in total_adj at line 618. |
| `app/core/service.py` | Pipeline wiring: injury fetch + pass to scoring | VERIFIED | Imports at lines 14/16, parallel fetch at line 75, 3-tuple return at line 177, score_snapshot wiring at lines 349-420. |
| `app/web/presentation.py` | Injury display on game cards | VERIFIED | CSS at lines 310-327, `renderInjurySection()` at lines 1540-1566, called in card template at line 1706. |
| `tests/core/test_agents.py` | Integration tests for injury adjustment in EdgeScoringAgent | VERIFIED | 279 lines, 3 new injury tests added. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/data/injuries.py` | `app/data/nhl_api.py` | `from app.data.nhl_api import _fetch_json` | WIRED | Line 13 |
| `app/core/injury_impact.py` | `app/data/injuries.py` | Lazy import of `fetch_team_player_stats` | WIRED | Line 159 in `build_player_tiers` |
| `app/core/service.py` | `app/data/injuries.py` | `from app.data.injuries import fetch_injuries` | WIRED | Line 14 |
| `app/core/service.py` | `app/core/injury_impact.py` | `from app.core.injury_impact import build_player_tiers` | WIRED | Line 16 |
| `app/core/agents.py` | `_estimate_win_probability` | `injury_adj: float = 0.0` parameter | WIRED | Line 575, used at line 618 |
| `app/web/web_preview.py` | `app/core/injury_impact.py` | `from app.core.injury_impact import build_player_tiers, calculate_injury_adjustment` | WIRED | Line 39 |
| `app/web/presentation.py` | card template | `renderInjurySection(g)` called in card HTML | WIRED | Line 1706 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| R4.1 | 05-01 | Fetch daily injury reports from NHL API | SATISFIED | `fetch_injuries()` fetches from ESPN injuries API; `fetch_team_player_stats()` fetches from NHL club-stats API. Parallel fetch in pipeline. |
| R4.2 | 05-01 | Tiered impact: top-6 F, top-4 D, starting G adjustments | SATISFIED | `classify_player_tier()` ranks by TOI within positional group. 5 tiers implemented with `TIER_IMPACT` constants. |
| R4.3 | 05-01, 05-02 | Win probability adjustment based on missing player value | SATISFIED | `calculate_injury_adjustment()` computes net pp adjustment; `EdgeScoringAgent` applies via `injury_adj` parameter. |
| R4.4 | 05-01, 05-02 | Manual override capability (existing overrides.json extended) | SATISFIED | `apply_overrides()` runs before injury adjustments in `score_snapshot()`. Injury adjustments are additive and separate. |

No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No anti-patterns detected |

No TODOs, FIXMEs, placeholders, or stub implementations found in any phase files.

### Human Verification Required

### 1. Live Injury Data Display

**Test:** Run `python tracker.py --tonight` on a game day and check output for injury adjustment logging.
**Expected:** Log lines showing injury fetch count, tier classifications, and any adjustment values applied to games.
**Why human:** Requires live ESPN API data to verify real-world parsing and display.

### 2. Dashboard Injury Cards

**Test:** Open the web dashboard on a game day with active injuries.
**Expected:** Game cards show "Key Out: [LastName] (IR/DTD/OUT)" below team names for top-tier injuries. Games with >2pp injury swing show a colored badge.
**Why human:** Visual rendering of CSS styling and layout within game cards cannot be verified programmatically.

### Gaps Summary

No gaps found. All 13 observable truths verified. All 8 artifacts exist, are substantive, and are wired. All 7 key links confirmed. All 4 requirements (R4.1-R4.4) satisfied. 564 tests pass with zero regressions. No anti-patterns detected.

---

_Verified: 2026-03-07T23:45:00Z_
_Verifier: Claude (gsd-verifier)_
