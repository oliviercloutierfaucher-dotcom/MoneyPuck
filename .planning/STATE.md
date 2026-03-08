---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Completed 06-01-PLAN.md
last_updated: "2026-03-08T00:01:00.000Z"
progress:
  total_phases: 11
  completed_phases: 5
  total_plans: 10
  completed_plans: 10
---

# Project State

## Current Milestone
**Milestone 1: Production-Ready Platform**

## Current Phase
**Phase 6: FastAPI Migration** — Plan 1/2 complete

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

## Key Context
- CI/CD pipeline active: GitHub Actions + Railway "Wait for CI" (Phase 2 complete)
- FastAPI app created alongside old stdlib server (Phase 6 Plan 1 complete)
- Jinja2 template replaces f-string for FastAPI rendering path
- Old web_preview.py still active until Phase 6 Plan 2 switches over
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

## Blockers
(none)

## Last Session
- **Stopped at:** Completed 06-01-PLAN.md
- **Timestamp:** 2026-03-08T00:01:00Z

## Performance Metrics

| Phase-Plan | Duration | Tasks | Files |
|-----------|----------|-------|-------|
| 06-01     | 6m32s    | 2     | 3     |

---
*Last updated: 2026-03-08*
