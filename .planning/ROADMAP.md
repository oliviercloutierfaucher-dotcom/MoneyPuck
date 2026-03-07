# Roadmap — Milestone 1: Production-Ready Platform

## Phase Overview

| # | Phase | Requirements | Risk | Parallel? |
|---|-------|-------------|------|-----------|
| 1 | Persistent Storage | R1 | P0 — data loss on every deploy | No (foundation) |
| 2 | CI/CD Pipeline | R8 | P2 — safety net before big changes | No (quick win) |
| 3 | Multi-Season Validation | R2 | P0 — model trust | No (blocks model work) |
| 4 | 2/2 | Complete   | 2026-03-07 | Yes (with 5) |
| 5 | Injury Impact System | R4 | P1 — second-highest impact | Yes (with 4) |
| 6 | FastAPI Migration | R5.1-R5.2 | P1 — backend swap | No (breaks web layer) |
| 7 | Dashboard Rebuild | R5.3-R5.7 | P1 — professional UI | No (depends on 6) |
| 8 | Automated Operations | R6 | P1 — reliability | No (depends on 1, 6) |
| 9 | Live Performance Tracking | R7 | P2 — proof of results | No (depends on 1, 8) |
| 10 | User Auth & Payments | R9 | P2 — monetization | No (depends on 6) |
| 11 | XGBoost Ensemble | R10 | P3 — model ceiling | No (depends on 3) |

---

## Phase 1: Persistent Storage

**Goal:** Stop losing data on Railway deploys.

**Requirements:** R1.1, R1.2, R1.3

**Plans:** 2 plans

Plans:
- [ ] 01-01-PLAN.md — Railway-aware DB path resolution, Dockerfile update, and odds response caching
- [ ] 01-02-PLAN.md — Railway volume configuration and deploy verification (checkpoint)

**Approach:**
- Add Railway volume mount at `/data`
- Update `database.py` to use `/data/tracker.db` when `RAILWAY_VOLUME_MOUNT_PATH` env var is set
- Add server-side odds response caching (90s TTL) to reduce API credit burn
- Test: deploy twice, verify data survives

**Success:** Predictions persist across 3 consecutive deploys.

---

## Phase 2: CI/CD Pipeline

**Goal:** Safety net before making big changes.

**Requirements:** R8.1, R8.2, R8.3

**Plans:** 1 plan

Plans:
- [x] 02-01-PLAN.md — Fix failing test, add CI workflow, enable Railway deploy gating

**Approach:**
- Add `.github/workflows/ci.yml` — run pytest on push and PR
- Configure Railway to deploy only after CI passes
- Verify test suite runs in <60s

**Success:** Broken code blocked from production.

---

## Phase 3: Multi-Season Validation

**Goal:** Prove the model works across multiple seasons, not just one.

**Requirements:** R2.1, R2.2, R2.3, R2.4

**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — Multi-season data loader, historical team codes, Elo carry-over support
- [ ] 03-02-PLAN.md — Walk-forward orchestrator, parameter stability analysis, verdict report, CLI integration

**Approach:**
- Extend backtester to load 2022-23, 2023-24 MoneyPuck data
- Walk-forward: train on prior seasons, test on next
- Report parameter stability (does home_advantage=0.14 hold?)
- Document whether current grid search params are overfit

**Success:** Model maintains >55% win rate on held-out seasons.

---

## Phase 4: Starting Goalies

**Goal:** Use confirmed starting goalies instead of GP-leader heuristic.

**Requirements:** R3.1, R3.2, R3.3, R3.4

**Plans:** 2/2 plans complete

Plans:
- [ ] 04-01-PLAN.md — DailyFaceoff scraper, NHL API gamecenter goalie enrichment, 3-tier resolution logic
- [ ] 04-02-PLAN.md — Pipeline integration into TeamStrengthAgent, starter_source labeling, backup-start Brier validation

**Approach:**
- Add goalie confirmation fetcher (DailyFaceoff scraper or NHL API)
- Integrate confirmed goalie save%/GSAx into TeamStrengthAgent
- Fallback to current GP-leader when confirmation unavailable
- Backtest with historical goalie data to measure improvement

**Success:** Brier score improves >0.005.

**Parallel with:** Phase 5

---

## Phase 5: Injury Impact System

**Goal:** Adjust win probability when key players are injured.

**Requirements:** R4.1, R4.2, R4.3, R4.4

**Approach:**
- Fetch injury reports from NHL API (already partially in nhl_api.py)
- Build tiered impact table: top-6 F (~1.5-2.5 pp), top-4 D (~1-2 pp), starting G (~2-5 pp)
- Apply adjustment in EdgeScoringAgent alongside situational factors
- Extend overrides.json for manual injury overrides

**Success:** Model adjusts correctly for missing star players.

**Parallel with:** Phase 4

---

## Phase 6: FastAPI Migration

**Goal:** Replace stdlib HTTP server with FastAPI for proper web framework.

**Requirements:** R5.1, R5.2

**Approach:**
- Install fastapi, uvicorn, jinja2
- Convert `web_preview.py` do_GET routes to `@app.get()` decorators
- Extract presentation.py f-string HTML into Jinja2 templates
- Update Dockerfile CMD to uvicorn
- All existing API endpoints preserved

**Success:** Same functionality, served by FastAPI with Jinja2 templates.

---

## Phase 7: Dashboard Rebuild

**Goal:** Professional multi-page dashboard with modern UI.

**Requirements:** R5.3, R5.4, R5.5, R5.6, R5.7

**Approach:**
- Add Tailwind CSS via CDN + DaisyUI components
- Multi-page routing: /games, /value-bets, /arbs, /performance, /props
- HTMX for partial updates (game cards, odds tables)
- SSE endpoint for real-time odds push
- Mobile-responsive with card-based layout
- TradingView Lightweight Charts for line movement
- Chart.js for P&L and performance graphs

**Success:** Dashboard looks comparable to BetQL/Betstamp.

---

## Phase 8: Automated Operations

**Goal:** Settlement and model updates run automatically.

**Requirements:** R6.1, R6.2, R6.3, R6.4, R6.5

**Approach:**
- Create `app/cron/runner.py` with --task flag
- Railway cron service: settle at 10:30 UTC, refresh at 16:00 UTC
- /health endpoint checking data freshness + last settlement time
- Add Odds API response caching (in-memory or Redis)
- Log alerts when data sources return errors

**Success:** Settlement runs automatically for 2 weeks.

---

## Phase 9: Live Performance Tracking

**Goal:** Public proof that the model makes money.

**Requirements:** R7.1, R7.2, R7.3, R7.4

**Approach:**
- Public /performance page (no auth required)
- Daily P&L chart, cumulative ROI, win rate, total bets
- Monthly/weekly breakdowns in table format
- CLV summary: % of bets that beat closing line
- Data comes from automated settlement (Phase 8)

**Success:** 30+ days of tracked live performance visible.

---

## Phase 10: User Auth & Payments

**Goal:** Gate premium features behind a paid subscription.

**Requirements:** R9.1, R9.2, R9.3, R9.4, R9.5

**Approach:**
- Supabase Auth: Google/GitHub OAuth + email/password
- JWT verification middleware in FastAPI
- Free tier: game cards + model probability (blurred value bets, no sizing)
- Paid tier ($29/mo via Stripe): full access to everything
- Stripe webhook for subscription management

**Success:** Users can sign up, free sees limited data, paid sees all.

---

## Phase 11: XGBoost Ensemble

**Goal:** Push model accuracy closer to the NHL prediction ceiling.

**Requirements:** R10.1, R10.2, R10.3

**Approach:**
- Train XGBoost on team metrics + Elo + goalie + injury features
- Ensemble weights tuned via walk-forward validation
- Compare Brier score, ROI, and calibration against current model
- Only deploy if statistically significant improvement

**Success:** Brier score improves >0.01 on multi-season validation.

---

## Dependency Graph

```
Phase 1 (Storage) ──► Phase 8 (Automation) ──► Phase 9 (Performance)
                  ──► Phase 6 (FastAPI) ──► Phase 7 (Dashboard)
                                        ──► Phase 8 (Automation)
                                        ──► Phase 10 (Auth)
Phase 2 (CI/CD) ──► All subsequent phases
Phase 3 (Validation) ──► Phase 11 (XGBoost)
Phase 4 (Goalies) ─┐
Phase 5 (Injuries) ─┤──► Phase 11 (XGBoost) — needs new features as inputs
```

---

*Roadmap created: 2026-03-06*
