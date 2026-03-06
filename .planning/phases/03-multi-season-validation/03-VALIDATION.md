---
phase: 3
slug: multi-season-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pytest discovery (no explicit config) |
| **Quick run command** | `python -m pytest tests/core/test_multi_season.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/core/test_multi_season.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | R2.1 | unit | `pytest tests/core/test_multi_season.py::test_load_multiple_seasons -x` | Wave 0 | pending |
| 03-01-02 | 01 | 1 | R2.1 | unit | `pytest tests/core/test_multi_season.py::test_graceful_season_fallback -x` | Wave 0 | pending |
| 03-01-03 | 01 | 1 | R2.2 | unit | `pytest tests/core/test_multi_season.py::test_walk_forward_validation -x` | Wave 0 | pending |
| 03-01-04 | 01 | 1 | R2.2 | unit | `pytest tests/core/test_multi_season.py::test_elo_carry_over -x` | Wave 0 | pending |
| 03-01-05 | 01 | 1 | R2.3 | unit | `pytest tests/core/test_multi_season.py::test_parameter_stability -x` | Wave 0 | pending |
| 03-01-06 | 01 | 1 | R2.3 | unit | `pytest tests/core/test_multi_season.py::test_verdict_logic -x` | Wave 0 | pending |
| 03-01-07 | 01 | 1 | R2.4 | unit | `pytest tests/core/test_multi_season.py::test_per_season_metrics -x` | Wave 0 | pending |
| 03-01-08 | 01 | 1 | R2.4 | unit | `pytest tests/core/test_multi_season.py::test_covid_season_flag -x` | Wave 0 | pending |

---

## Wave 0 Requirements

- [ ] `tests/core/test_multi_season.py` — covers R2.1, R2.2, R2.3, R2.4
- [ ] Tests must use synthetic data (not live MoneyPuck fetches) for speed and reliability

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full multi-season run with real data | R2.1-R2.4 | Requires MoneyPuck API access, slow | Run `python tracker.py --validate` and inspect output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
