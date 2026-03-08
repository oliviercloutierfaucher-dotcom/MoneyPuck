# Requirements

## Milestone 1: Production-Ready Platform

**Goal:** Transform MoneyPuck from a working prototype into a professional, reliable product that proves its value with real tracked performance.

**Priority order:** Fix data loss → Validate model → Improve model → Rebuild UI → Add auth/payments

---

### R1: Persistent Data Storage (P0 — Data Loss)
SQLite data is lost on every Railway deploy (ephemeral filesystem). Predictions, bet history, and CLV data disappear.
- **R1.1** Mount a Railway volume or migrate to Railway-managed PostgreSQL
- **R1.2** Existing SQLite schema migrates cleanly to new storage
- **R1.3** Bet history, predictions, and settlement data survive deploys
- **Success:** Data persists across 3 consecutive Railway deploys

### R2: Multi-Season Model Validation (P0 — Trust)
Model is only validated on 2024-25 season. Grid search parameters may be overfit.
- **R2.1** Backtester supports 2022-23, 2023-24, and 2024-25 seasons
- **R2.2** Walk-forward validation: train on season N, test on N+1
- **R2.3** Parameter stability report: do optimal params hold across seasons?
- **R2.4** Brier score, ROI, win rate reported per season
- **Success:** Model maintains >55% win rate and positive ROI on held-out seasons

### R3: Confirmed Starting Goalies (P1 — Model Accuracy)
Current GP-leader heuristic is wrong ~25% of the time. Goalie identity is the highest-impact missing signal.
- **R3.1** Fetch confirmed starters from DailyFaceoff or NHL API
- **R3.2** Use confirmed goalie's actual save%/GSAx instead of GP-leader's
- **R3.3** Graceful fallback to GP-leader when no confirmation available
- **R3.4** Timing: data available by early afternoon on game days
- **Success:** Brier score improves by >0.005 on backtested data

### R4: Injury Impact System (P1 — Model Accuracy)
Zero roster awareness. Missing McDavid is treated same as full-health.
- **R4.1** Fetch daily injury reports from NHL API
- **R4.2** Tiered impact: top-6 F, top-4 D, starting G adjustments
- **R4.3** Win probability adjustment based on missing player value
- **R4.4** Manual override capability (existing overrides.json extended)
- **Success:** Model correctly adjusts probability when key players are out

### R5: Professional Web Dashboard (P1 — Presentation)
Single-file f-string HTML is unmaintainable and looks amateur.
- [x] **R5.1** Migrate backend to FastAPI + Uvicorn (keep existing pipeline)
- [x] **R5.2** Extract HTML to Jinja2 templates (proper .html files)
- **R5.3** Multi-page routing: Tonight's Games, Value Bets, Arbs, Performance, Props
- **R5.4** Tailwind CSS for professional styling (CDN, no build step)
- **R5.5** HTMX for dynamic partial updates (replace full-page refresh)
- **R5.6** Mobile-responsive layout
- **R5.7** Real-time odds updates via SSE (replace 60s polling)
- **Success:** Dashboard looks comparable to BetQL/Betstamp on desktop and mobile

### R6: Automated Operations (P1 — Reliability)
Settlement is manual. No monitoring. No scheduling.
- **R6.1** Railway cron service for automated daily settlement (10:30 UTC)
- **R6.2** Automated model refresh (Elo + team strength, 16:00 UTC)
- **R6.3** Health check endpoint (/health) with data freshness validation
- **R6.4** Odds API response caching to reduce costs
- **R6.5** Alert logging when data sources fail
- **Success:** Settlement runs daily without manual intervention for 2 weeks

### R7: Live Performance Tracking (P2 — Proof)
No public proof that the model works. Critical for building trust.
- **R7.1** Public performance page: ROI, win rate, total bets, streak
- **R7.2** Results updated daily after settlement
- **R7.3** Monthly and weekly breakdowns
- **R7.4** CLV summary (% of bets beating closing line)
- **Success:** 30+ days of tracked live performance visible on site

### R8: CI/CD Pipeline (P2 — Quality)
No automated testing on push. No deploy gate.
- [x] **R8.1** GitHub Actions workflow: run pytest on push/PR
- [x] **R8.2** Railway waits for CI pass before deploying
- [x] **R8.3** Test suite runs in <60 seconds (23s achieved)
- **Success:** Broken code cannot reach production

### R9: User Authentication (P2 — Monetization Prep)
Anyone with URL sees everything. Needed before paid tiers.
- **R9.1** Supabase Auth integration (Google/GitHub OAuth + email)
- **R9.2** JWT verification middleware in FastAPI
- **R9.3** Free tier: game scores + model probability (no sizing, no arbs)
- **R9.4** Paid tier: full value bets, Kelly, arbs, hedge, CLV, performance
- **R9.5** Stripe subscription ($29/mo) for paid tier
- **Success:** Users can sign up, free users see limited data, paid users see everything

### R10: XGBoost Ensemble (P3 — Model Ceiling)
Logistic regression limits calibration. XGBoost should improve Brier score.
- **R10.1** Train XGBoost on team metrics + Elo + situational features
- **R10.2** Ensemble: logistic + Elo + XGBoost (weights tuned via backtest)
- **R10.3** Walk-forward validation proves improvement over current model
- **Success:** Brier score improves by >0.01 on multi-season validation

---

## Out of Scope (Milestone 1)

- Mobile native app
- Non-NHL sports
- Social features / community
- Full WAR/GAR integration (Phase 2 of injury system)
- Neural network models
- French language compliance (Bill 96 — needs lawyer)
