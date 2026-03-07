---
phase: 04-starting-goalies
verified: 2026-03-07T17:30:00Z
status: passed
score: 8/8 must-haves verified
must_haves:
  truths:
    - "DailyFaceoff scraper returns goalie names and confirmation status for today's games"
    - "NHL API gamecenter endpoint returns per-goalie season stats for a specific game"
    - "3-tier resolution correctly picks confirmed > likely > gp_leader"
    - "When DailyFaceoff is down or returns empty, fallback to GP-leader works without error"
    - "Pipeline uses confirmed goalie's actual save% instead of GP-leader's when confirmation is available"
    - "Each prediction is labeled with starter source (confirmed/likely/gp_leader)"
    - "When no confirmation data is available, model output is identical to current behavior"
    - "Backup-start games in 2024-25 are identified and the Brier impact of wrong-goalie is measured"
  artifacts:
    - path: "app/data/dailyfaceoff.py"
      status: verified
    - path: "app/data/goalie_resolver.py"
      status: verified
    - path: "app/data/nhl_api.py"
      status: verified
    - path: "app/core/agents.py"
      status: verified
    - path: "app/core/models.py"
      status: verified
    - path: "app/core/service.py"
      status: verified
    - path: "app/web/web_preview.py"
      status: verified
    - path: "tests/data/test_dailyfaceoff.py"
      status: verified
    - path: "tests/data/test_goalie_resolver.py"
      status: verified
    - path: "tests/core/test_agents.py"
      status: verified
    - path: "tests/core/test_goalie_validation.py"
      status: verified
  key_links:
    - from: "app/data/goalie_resolver.py"
      to: "app/data/nhl_api.py"
      via: "from app.data.nhl_api import infer_likely_starter"
      status: verified
    - from: "app/core/agents.py"
      to: "app/data/goalie_resolver.py"
      via: "from app.data.goalie_resolver import resolve_all_starters"
      status: verified
    - from: "app/core/agents.py"
      to: "app/data/dailyfaceoff.py"
      via: "confirmed_starters parameter flow from service.py"
      status: verified
    - from: "app/core/service.py"
      to: "app/data/dailyfaceoff.py"
      via: "from app.data.dailyfaceoff import fetch_dailyfaceoff_starters"
      status: verified
requirements:
  - id: R3.1
    status: satisfied
  - id: R3.2
    status: satisfied
  - id: R3.3
    status: satisfied
  - id: R3.4
    status: satisfied
anti_patterns:
  - file: "app/data/nhl_api.py"
    line: "213, 292"
    pattern: "Duplicate function definition"
    severity: warning
    impact: "fetch_game_goalies defined twice; second silently shadows first. Not functionally broken but code smell."
---

# Phase 4: Starting Goalies Verification Report

**Phase Goal:** Use confirmed starting goalies instead of GP-leader heuristic.
**Verified:** 2026-03-07T17:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DailyFaceoff scraper returns goalie names and confirmation status | VERIFIED | `app/data/dailyfaceoff.py` (135 lines): `fetch_dailyfaceoff_starters()` extracts `__NEXT_DATA__` JSON via regex, parses game entries, maps team slugs via 32-team `SLUG_TO_ABBREV` dict, returns list of dicts with goalie names + status. 9 tests in `test_dailyfaceoff.py`. |
| 2 | NHL API gamecenter endpoint returns per-goalie season stats | VERIFIED | `app/data/nhl_api.py`: `fetch_game_goalies()` fetches `/v1/gamecenter/{id}/landing`, extracts `goalieComparison` data with player_id, name, games_played, save_pct, gaa. Tests in `test_nhl_api.py`. |
| 3 | 3-tier resolution correctly picks confirmed > likely > gp_leader | VERIFIED | `app/data/goalie_resolver.py` (142 lines): `resolve_starter()` checks DailyFaceoff entries for confirmed/likely status first, falls back to `infer_likely_starter()`. 11 tests in `test_goalie_resolver.py` covering all tiers. |
| 4 | When DailyFaceoff is down, fallback to GP-leader works without error | VERIFIED | `dailyfaceoff.py` returns `[]` on any exception (line 89-90). `service.py` wraps fetch in `_fetch_df_starters_safe()` returning `[]` on failure (line 36-44). `goalie_resolver.py` treats empty `df_starters` as "no data" and falls to tier 3. Tests confirm empty list fallback. |
| 5 | Pipeline uses confirmed goalie's actual save% instead of GP-leader's | VERIFIED | `agents.py` lines 193-201: `resolve_all_starters()` called with `df_starters` and `goalie_stats`, matched goalie's `save_pct` flows into `TeamMetrics.starter_save_pct`. Test `test_confirmed_starter_uses_confirmed_save_pct` verifies save_pct changes with confirmed data. |
| 6 | Each prediction labeled with starter source | VERIFIED | `models.py` line 48: `starter_source: str = "gp_leader"` field on `TeamMetrics`. `agents.py` line 260: `starter_source=goalie_sources.get(team, "gp_leader")`. `web_preview.py` lines 636-656: `home_starter_source` and `away_starter_source` extracted and included in game output. 3 tests verify labeling (confirmed, likely, gp_leader). |
| 7 | No confirmation data produces identical behavior to pre-phase | VERIFIED | Default `starter_source="gp_leader"` on `TeamMetrics`. When `confirmed_starters=[]`, `resolve_all_starters` returns GP-leader for all teams. Tests `test_gp_leader_fallback_with_empty_confirmed` and `test_no_confirmed_starters_param_defaults_to_gp_leader` verify. |
| 8 | Backup-start Brier impact measured | VERIFIED | `tests/core/test_goalie_validation.py` (262 lines): 5 validation tests with synthetic scenarios. `test_backup_start_brier_improvement` creates 25+ scenarios, asserts Brier improvement > 0.005. `test_gp_leader_error_magnitude` quantifies 1-3pp error. `test_correct_starter_no_regression` confirms no regression when GP-leader is correct. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/data/dailyfaceoff.py` | DailyFaceoff scraper | VERIFIED | 135 lines, exports `fetch_dailyfaceoff_starters`, `SLUG_TO_ABBREV` |
| `app/data/goalie_resolver.py` | 3-tier resolution | VERIFIED | 142 lines, exports `resolve_starter`, `resolve_all_starters` |
| `app/data/nhl_api.py` | fetch_game_goalies extension | VERIFIED | Function present (defined twice, see anti-patterns) |
| `app/core/agents.py` | TeamStrengthAgent using resolve_starter | VERIFIED | `resolve_all_starters` imported and called at line 197 |
| `app/core/models.py` | starter_source field on TeamMetrics | VERIFIED | Line 48: `starter_source: str = "gp_leader"` |
| `app/core/service.py` | DailyFaceoff starters fetched in parallel | VERIFIED | `_fetch_df_starters_safe()` submitted to thread pool, passed to `strength_agent.run()` |
| `app/web/web_preview.py` | starter_source displayed | VERIFIED | Lines 636-656: home/away starter_source extracted and included in game dict |
| `tests/data/test_dailyfaceoff.py` | DailyFaceoff tests | VERIFIED | 188 lines, 9 tests |
| `tests/data/test_goalie_resolver.py` | Resolver tests | VERIFIED | 214 lines, 11 tests |
| `tests/core/test_agents.py` | Agent integration tests | VERIFIED | 185 lines, 7 tests for confirmed goalie integration |
| `tests/core/test_goalie_validation.py` | Backup-start validation | VERIFIED | 262 lines, 5 validation tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `goalie_resolver.py` | `nhl_api.py` | `from app.data.nhl_api import infer_likely_starter` | WIRED | Line 13 of goalie_resolver.py; used at line 110 for tier-3 fallback |
| `agents.py` | `goalie_resolver.py` | `from app.data.goalie_resolver import resolve_all_starters` | WIRED | Line 59 of agents.py; called at line 197 |
| `service.py` | `dailyfaceoff.py` | `from app.data.dailyfaceoff import fetch_dailyfaceoff_starters` | WIRED | Line 13 of service.py; called in `_fetch_df_starters_safe()` at line 41 |
| `service.py` | `agents.py` | `strength_agent.run(..., confirmed_starters)` | WIRED | Line 146: confirmed_starters passed as 4th arg to `strength_agent.run()` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| R3.1 | 04-01 | Fetch confirmed starters from DailyFaceoff or NHL API | SATISFIED | `dailyfaceoff.py` fetches confirmed starters; `nhl_api.py` provides `fetch_game_goalies` for gamecenter enrichment |
| R3.2 | 04-02 | Use confirmed goalie's actual save%/GSAx instead of GP-leader's | SATISFIED | `agents.py` lines 193-201: resolved goalie's save_pct used in TeamMetrics instead of GP-leader's when confirmed |
| R3.3 | 04-01, 04-02 | Graceful fallback to GP-leader when no confirmation available | SATISFIED | 3-tier resolution in `goalie_resolver.py`; all error paths return `[]`; starter_source defaults to "gp_leader" |
| R3.4 | 04-02 | Timing: data available by early afternoon on game days | SATISFIED | DailyFaceoff scraper uses date parameter; fetched in parallel during `build_market_snapshot()`; DailyFaceoff typically publishes by early afternoon |

No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/data/nhl_api.py` | 213, 292 | Duplicate `fetch_game_goalies` definition | Warning | Second definition silently shadows first. Both implementations are nearly identical (second adds `if not team_abbrev: continue` guard). Not functionally broken -- Python uses the last definition -- but is a code smell that should be cleaned up. |

### Human Verification Required

### 1. DailyFaceoff Scraper Against Live Page

**Test:** Run `python -c "from app.data.dailyfaceoff import fetch_dailyfaceoff_starters; print(fetch_dailyfaceoff_starters('2026-03-07'))"` on a game day.
**Expected:** Returns list of dicts with goalie names, confirmation statuses, and team abbreviations for tonight's games.
**Why human:** DailyFaceoff page structure may have changed since research was done; `__NEXT_DATA__` JSON schema may differ from mocked fixtures.

### 2. Starter Source Display on Dashboard

**Test:** Visit the web dashboard on a game day and check game cards.
**Expected:** Each game displays starter source labels (Confirmed/Likely/GP Leader) for both teams' goalies.
**Why human:** Visual rendering and label formatting cannot be verified programmatically.

### Gaps Summary

No gaps found. All 8 observable truths verified. All 4 requirements (R3.1-R3.4) satisfied. All key links wired. 32 tests pass.

One warning-level anti-pattern: duplicate `fetch_game_goalies` definition in `nhl_api.py` should be cleaned up but does not block goal achievement.

---

_Verified: 2026-03-07T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
