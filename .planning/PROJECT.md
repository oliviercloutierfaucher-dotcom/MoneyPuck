# MoneyPuck

## What This Is

An NHL betting edge platform that combines advanced analytics (MoneyPuck xG, Elo ratings, situational adjustments) with real-time odds from multiple sportsbooks to identify value bets, arbitrage opportunities, and line movement. Deployed as a web dashboard on Railway with a CLI for power users. Target audience: serious NHL bettors who want data-driven picks, and casual fans who want guidance on tonight's games.

## Core Value

The model must produce profitable picks over time — accurate win probabilities that consistently find edges against the market. Everything else (design, features, monetization) is worthless if the picks don't work.

## Requirements

### Validated

- ✓ 6-agent scoring pipeline (odds → stats → strength → edge → line shop → risk) — existing
- ✓ 16 team metrics with exponential decay weighting — existing
- ✓ Elo rating system (25% Elo + 75% logistic ensemble) — existing
- ✓ Goalie matchup and situational adjustments (B2B, timezone) — existing
- ✓ Half-Kelly bet sizing with 3% per-bet cap — existing
- ✓ Web dashboard with game cards, value bets, model vs street — existing
- ✓ Arbitrage scanner (ML, spread, total) with cross-book validation — existing
- ✓ Hedge calculator — existing
- ✓ CLV tracking — existing
- ✓ Line movement sparklines — existing
- ✓ Player props display — existing
- ✓ Bet tracker / performance dashboard — existing
- ✓ Light/dark theme toggle — existing
- ✓ Sportsbook deep links (Quebec region support) — existing
- ✓ Demo mode when no API key — existing
- ✓ CLI with --tonight, --arbs, --backtest, --army modes — existing
- ✓ SQLite persistence for predictions, settlement, closing odds — existing
- ✓ Backtesting framework with grid search — existing
- ✓ Railway deployment (Docker) — existing
- ✓ 440+ tests — existing

### Active

- [ ] Multi-season model validation (beyond single 2024-25 season)
- [ ] Additional prediction signals (injuries, rest days, goalie confirmation, travel)
- [ ] Model calibration and Brier score improvement
- [ ] Professional web UI rebuild (proper routing, responsive design, polished look)
- [ ] User authentication and accounts
- [ ] Free/paid tier split (free: basic picks, paid: full model + tools)
- [ ] Live-tracked performance with public proof of results
- [ ] Real-time line movement alerts
- [ ] Mobile-responsive design
- [ ] Automated settlement and daily P&L reporting

### Out of Scope

- Mobile native app — web-first, responsive design covers mobile
- Non-NHL sports — stay focused on one sport and do it well
- Social features / community — this is a tool, not a social network
- Manual handicapping content — model-driven only, no editorial picks

## Context

- Current model: 18.6% ROI, 60.1% win rate, Brier 0.2430 on 2024-25 season backtest
- Parameters tuned via grid search: home_advantage=0.14, logistic_k=0.9
- Dashboard is a single-file Python HTML generator (presentation.py) — works but hard to maintain
- No user auth — anyone with the Railway URL sees everything
- MoneyPuck bulk CSV endpoint is dead (403) — using per-team CSVs with User-Agent header
- Odds API has rate limits and costs per request
- Quebec region book support (Betway, Bet365, Pinnacle, etc.)

## Constraints

- **Stack**: Python backend, keep existing agent pipeline architecture
- **Data**: MoneyPuck CSVs + Odds API + NHL API + Polymarket (no paid data feeds yet)
- **Deployment**: Railway (Docker), must respect PORT env var
- **Budget**: Odds API has usage-based pricing — minimize unnecessary calls
- **Auth**: Need a solution that works with Python stdlib HTTP server (no Django/Flask dependency currently)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python-only stack (no JS framework) | Keeps deployment simple, single Dockerfile | — Pending |
| Elo ensemble at 25/75 blend | Grid search showed this optimal for 2024-25 | — Pending |
| Half-Kelly sizing | Full Kelly too aggressive, quarter too conservative | ✓ Good |
| SQLite for persistence | Simple, no external DB needed on Railway | — Pending |
| Quebec region default | User is in Quebec, books match local market | ✓ Good |

---
*Last updated: 2026-03-06 after initialization*
