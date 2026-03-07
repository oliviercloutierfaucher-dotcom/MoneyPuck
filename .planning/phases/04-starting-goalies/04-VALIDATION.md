---
phase: 4
slug: starting-goalies
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pytest discovery (no explicit config) |
| **Quick run command** | `python -m pytest tests/data/test_goalie_confirmation.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/data/test_goalie_confirmation.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | R3.1 | unit | `pytest tests/data/test_goalie_confirmation.py::test_fetch_confirmed_starters -x` | Wave 0 | pending |
| 04-01-02 | 01 | 1 | R3.2 | unit | `pytest tests/data/test_goalie_confirmation.py::test_use_confirmed_goalie_stats -x` | Wave 0 | pending |
| 04-01-03 | 01 | 1 | R3.3 | unit | `pytest tests/data/test_goalie_confirmation.py::test_fallback_to_gp_leader -x` | Wave 0 | pending |
| 04-01-04 | 01 | 1 | R3.4 | unit | `pytest tests/data/test_goalie_confirmation.py::test_timing_availability -x` | Wave 0 | pending |
| 04-02-01 | 02 | 2 | R3.2 | unit | `pytest tests/data/test_goalie_confirmation.py::test_brier_improvement -x` | Wave 0 | pending |

---

## Wave 0 Requirements

- [ ] `tests/data/test_goalie_confirmation.py` — covers R3.1, R3.2, R3.3, R3.4
- [ ] Tests must use synthetic/mock data (not live DailyFaceoff fetches) for speed and reliability

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live DailyFaceoff fetch | R3.1 | Requires live web access, page structure may change | Run `python -c "from app.data.nhl_api import fetch_confirmed_starters; print(fetch_confirmed_starters())"` on game day |
| Brier improvement on real data | R3.4 | Requires full backtest with real game data | Run backtest comparing with/without confirmed starters |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
