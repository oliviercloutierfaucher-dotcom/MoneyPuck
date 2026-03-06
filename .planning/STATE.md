# Project State

## Current Milestone
**Milestone 1: Production-Ready Platform**

## Current Phase
**Phase 2: CI/CD Pipeline** — Not started

## Completed Phases
- **Phase 1: Persistent Storage** — Complete (2026-03-06)
  - Railway volume at /data, RAILWAY_RUN_UID=0, 90s odds cache
  - 466 tests passing, data persists across deploys

## Key Context
- Model validated on single season only — multi-session validation needed (Phase 3)
- 466 tests passing, no CI/CD pipeline yet (Phase 2)
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
- **Stopped at:** Phase 1 complete, ready for Phase 2
- **Timestamp:** 2026-03-06T21:45:00Z

---
*Last updated: 2026-03-06*
