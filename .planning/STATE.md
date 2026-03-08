---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Completed 07-02-PLAN.md
last_updated: "2026-03-08T01:10:55.038Z"
progress:
  total_phases: 11
  completed_phases: 6
  total_plans: 14
  completed_plans: 13
  percent: 93
---

---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Completed 06-02-PLAN.md
last_updated: "2026-03-08T00:13:16.891Z"
progress:
  [█████████░] 93%
  completed_phases: 6
  total_plans: 11
  completed_plans: 11
---

---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Completed 06-02-PLAN.md
last_updated: "2026-03-08T00:10:00.000Z"
progress:
  total_phases: 11
  completed_phases: 6
  total_plans: 12
  completed_plans: 12
---

# Project State

## Current Milestone
**Milestone 1: Production-Ready Platform**

## Current Phase
**Phase 7: Dashboard Rebuild** — In Progress (1/? plans)

## Completed Phases
- **Phase 1: Persistent Storage** — Complete (2026-03-06)
  - Railway volume at /data, RAILWAY_RUN_UID=0, 90s odds cache
  - 466 tests passing, data persists across deploys
- **Phase 2: CI/CD Pipeline** — Complete (2026-03-06)
  - GitHub Actions + Railway "Wait for CI"
- **Phase 3: Multi-Season Validation** — Complete (2026-03-07)
  - Walk-forward validation, Elo ensemble, historical team codes
- **Phase 4: Starting Goalies** — Complete (2026-03-07)
  - DailyFaceoff scraper, 3-tier goalie resolution, pipeline integration
  - Confirmed goalies improve Brier by >0.005 on backup-start games
  - 528 tests passing
- **Phase 5: Injury Impact System** — Complete (2026-03-07)
  - ESPN injury fetcher, player tier classification, pipeline integration
  - Dashboard shows key injuries on game cards
- **Phase 6: FastAPI Migration** — Complete (2026-03-08)
  - FastAPI app with all routes, Jinja2 template, security middleware
  - Dockerfile updated to uvicorn, old stdlib server deleted
  - 575 tests passing

- **Phase 7: Dashboard Rebuild** — In Progress (2026-03-08)
  - HTMX tab shell with 5 partials, dual-mode route handlers
  - 607 tests passing

## Key Context
- CI/CD pipeline active: GitHub Actions + Railway "Wait for CI" (Phase 2 complete)
- FastAPI migration complete: app.web.app serves all routes via uvicorn
- Jinja2 template replaces f-string for FastAPI rendering path
- Old web_preview.py deleted -- all logic in app.web.app
- Research docs in `.planning/research/` cover model, frontend, auth, ops

## Decisions
- DB path resolution uses 3-tier priority: RAILWAY_VOLUME_MOUNT_PATH > MONEYPUCK_DB_PATH > ~/.moneypuck/tracker.db
- Odds caching at web_preview.py level only (CLI/backtester uncached)
- 90-second TTL for odds response cache
- Cache bypass via ?refresh=1 query param
- [Phase 02]: Single CI job, no matrix -- 466 tests in 11s
- [Phase 02]: Test deps in requirements.txt (no separate dev file)
- [Phase 03]: Historical team codes via era boundaries (ARI->UTA 2024, SEA 2021, VGK 2017)
- [Phase 03]: Elo carry-over via optional elo_tracker param with incremental game updates
- [Phase 03]: Reduced grid search to 81 combos per season; CV>0.3 threshold for drift; strict pass/fail requires >=55% accuracy AND positive ROI every season
- [Phase 04]: DailyFaceoff __NEXT_DATA__ JSON extraction over DOM scraping for stability
- [Phase 04]: Last-name + team_code matching for goalie name resolution across data sources
- [Phase 04]: Confirmed starters passed as parameter to TeamStrengthAgent.run() for testability
- [Phase 04]: DailyFaceoff fetched in parallel thread pool alongside odds and goalie stats
- [Phase 04]: starter_source defaults to gp_leader ensuring backward compatibility
- [Phase 05]: ESPN injuries API as primary injury data source (free, structured JSON, no auth)
- [Phase 05]: Goalie injuries excluded from adjustment (Phase 4 handles via backup save%)
- [Phase 05]: Last-name matching for player lookup between ESPN and NHL API data
- [Phase 05]: injury_adj in probability units (pp/100), not raw pp like goalie_adj
- [Phase 05]: Dashboard shows only top-tier injuries (top6_f, top4_d, starting_g) to avoid clutter
- [Phase 05]: build_market_snapshot returns 3-tuple (snapshot, games_rows, injuries) for transparency
- [Phase 06]: Sync route handlers (def, not async def) because pipeline uses blocking requests
- [Phase 06]: Keep render_dashboard() in presentation.py for CLI backward compatibility
- [Phase 06]: Jinja2 template is new rendering path for FastAPI; old f-string stays for CLI
- [Phase 06]: Security headers applied via middleware, matching existing PreviewHandler behavior
- [Phase 06]: Dockerfile CMD uses shell form for PORT env var interpolation
- [Phase 06]: Old web_preview.py fully deleted -- all logic lives in app.web.app

- [Phase 07]: HTMX via CDN (no npm/build step) for tab navigation with hx-push-url
- [Phase 07]: Dual-mode route pattern: _tab_response() checks HX-Request header
- [Phase 07]: Games partial carries all existing client-side JS for backward compatibility
- [Phase 07]: window.__MP_DATA provides global data access for cross-partial JS
- [Phase 07]: Game cards, plays, arbs, value bets table rendered server-side via Jinja2 macros from data dict
- [Phase 07]: Modal content still uses JS DOM building (complex interactive lookups); sparklines via data attributes
- [Phase 07]: Three CSS breakpoints: 1024px desktop, 768px tablet, 480px phone with 44px touch targets

## Blockers
(none)

## Last Session
- **Stopped at:** Completed 07-02-PLAN.md
- **Timestamp:** 2026-03-08T00:55:00Z

## Performance Metrics

| Phase-Plan | Duration | Tasks | Files |
|-----------|----------|-------|-------|
| 06-01     | 6m32s    | 2     | 3     |
| 06-02     | 4min     | 2     | 8     |
| 07-01     | 10min    | 2     | 10    |

---
*Last updated: 2026-03-08*
| Phase 07 P02 | 10min | 3 tasks | 5 files |

