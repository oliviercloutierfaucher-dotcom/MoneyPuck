---
phase: 06-fastapi-migration
plan: 01
subsystem: web
tags: [fastapi, jinja2, migration, api]
dependency_graph:
  requires: []
  provides: [fastapi-app, jinja2-template, api-routes]
  affects: [web-layer, deployment]
tech_stack:
  added: [fastapi, uvicorn, jinja2]
  patterns: [sync-route-handlers, security-middleware, exception-handlers]
key_files:
  created:
    - app/web/app.py
    - app/web/templates/base.html
  modified:
    - requirements.txt
decisions:
  - Sync route handlers (def, not async def) because pipeline uses blocking requests library
  - Keep render_dashboard() in presentation.py for CLI backward compatibility
  - Jinja2 template is new rendering path for FastAPI; old f-string stays for CLI
  - Security headers applied via middleware, matching existing PreviewHandler behavior
metrics:
  duration: 6m32s
  completed: 2026-03-07
---

# Phase 06 Plan 01: FastAPI App and Jinja2 Template Summary

FastAPI application with 5 route groups, security middleware, exception handlers, and Jinja2 template converted from 2252-line f-string.

## What Was Done

### Task 1: Create FastAPI app with all routes, middleware, and helpers

Created `app/web/app.py` with the complete FastAPI application:

- **Routes:** `/` and `/index.html` (HTML dashboard), `/api/dashboard`, `/api/performance`, `/api/opportunities`, `/api/odds-history`
- **Security middleware:** X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy on every response
- **Exception handlers:** ValueError -> 400, OSError/TimeoutError -> 502, Exception -> 500
- **Helper functions:** All business logic copied from web_preview.py (~900 lines): TTLCache, _build_demo_dashboard, _build_live_dashboard, _build_performance_data, _detect_arbs, _extract_value_bets_from_games, _demo_performance_data, _load_dotenv
- **Demo mode:** Activates when no ODDS_API_KEY or demo=1 query param
- **Updated requirements.txt:** Added fastapi>=0.115, uvicorn[standard]>=0.34, jinja2>=3.1

**Commit:** 2885c43

### Task 2: Convert presentation.py f-string to Jinja2 base.html template

Converted the 2252-line f-string from `render_dashboard()` into `app/web/templates/base.html`:

- Only one f-string interpolation existed (`{data_json}`) -- converted to `{{ data_json | safe }}`
- All CSS/JS escaped braces (`{{`/`}}`) unescaped to literal `{`/`}`
- JSDoc annotations (`{number}`, `{string}`) are inert in Jinja2
- Template renders 97,665 characters with empty data context
- presentation.py kept unchanged for backward compatibility (CLI rendering path)

**Commit:** 17053ea

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- `from app.web.app import app` -- imports successfully
- 10 routes registered (5 user routes + 4 built-in FastAPI routes + openapi)
- Jinja2 template renders without errors (97,665 chars)
- `pip install -r requirements.txt` succeeds
- 562 existing tests pass (no breakage)

## Decisions Made

1. **Sync handlers over async:** All route handlers use `def` (not `async def`) because the pipeline uses `requests` (blocking). FastAPI runs sync handlers in a thread pool automatically.
2. **Backward compatibility:** presentation.py's `render_dashboard()` kept intact. CLI uses the f-string path; FastAPI uses Jinja2. Phase 7 will unify.
3. **Template conversion approach:** Programmatic extraction + brace unescaping rather than manual rewrite of 2252 lines.

## Self-Check: PASSED
