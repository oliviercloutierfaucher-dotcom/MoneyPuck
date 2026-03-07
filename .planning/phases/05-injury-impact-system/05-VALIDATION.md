---
phase: 5
slug: injury-impact-system
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pytest discovery (no explicit config) |
| **Quick run command** | `python -m pytest tests/data/test_injuries.py tests/core/test_injury_impact.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/data/test_injuries.py tests/core/test_injury_impact.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | R4.1 | unit | `pytest tests/data/test_injuries.py::test_fetch_injuries -x` | Wave 0 | pending |
| 05-01-02 | 01 | 1 | R4.2 | unit | `pytest tests/data/test_injuries.py::test_classify_player_tier -x` | Wave 0 | pending |
| 05-02-01 | 02 | 2 | R4.3 | unit | `pytest tests/core/test_injury_impact.py::test_injury_adjustment -x` | Wave 0 | pending |
| 05-02-02 | 02 | 2 | R4.4 | unit | `pytest tests/core/test_injury_impact.py::test_override_coexistence -x` | Wave 0 | pending |

---

## Wave 0 Requirements

- [ ] `tests/data/test_injuries.py` — covers R4.1, R4.2
- [ ] `tests/core/test_injury_impact.py` — covers R4.3, R4.4
- [ ] Tests must use synthetic/mock data (not live ESPN fetches) for speed and reliability

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live ESPN injury fetch | R4.1 | Requires live web access, API may change | Run `python -c "from app.data.injuries import fetch_injuries; print(fetch_injuries())"` |
| Dashboard injury display | R4.3 | Visual verification needed | Start server and check game cards show injury info |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
