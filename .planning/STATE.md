# Project State

## Current Milestone
**Milestone 1: Production-Ready Platform**

## Current Phase
**Phase 1: Persistent Storage** — Plan 1/2 complete, executing Plan 2

## Completed Phases
(none — Phase 1 in progress)

## Key Context
- SQLite data loss on Railway deploys is P0 (Phase 1)
- Model validated on single season only — multi-session validation needed (Phase 3)
- 466 tests passing (11 new from Plan 01-01), no CI/CD pipeline yet (Phase 2)
- Dashboard is single-file f-string HTML — migrating to FastAPI + Jinja2 (Phase 6-7)
- Research docs in `.planning/research/` cover model, frontend, auth, ops

## Decisions
- DB path resolution uses 3-tier priority: RAILWAY_VOLUME_MOUNT_PATH > MONEYPUCK_DB_PATH > ~/.moneypuck/tracker.db
- Odds caching at web_preview.py level only (CLI/backtester uncached)
- 90-second TTL for odds response cache
- Cache bypass via ?refresh=1 query param

## Blockers
(none)

## Last Session
- **Stopped at:** Completed 01-01-PLAN.md (Persistent Storage Foundation)
- **Timestamp:** 2026-03-06T19:24:00Z

---
*Last updated: 2026-03-06*
