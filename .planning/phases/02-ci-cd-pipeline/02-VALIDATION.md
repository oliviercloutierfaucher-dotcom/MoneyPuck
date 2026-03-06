---
phase: 2
slug: ci-cd-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | none (defaults) |
| **Quick run command** | `python -m pytest -x -q --tb=short` |
| **Full suite command** | `python -m pytest -q --tb=short` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest -x -q --tb=short`
- **After every plan wave:** Run `python -m pytest -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | R8.1 | manual | Push to branch, check Actions tab | N/A | pending |
| 02-01-02 | 01 | 1 | R8.3 | smoke | `python -m pytest -q --tb=short` (check elapsed) | Yes | pending |
| 02-01-03 | 01 | 1 | R8.2 | manual | Push failing code, verify Railway skips deploy | N/A | pending |

---

## Wave 0 Requirements

- [ ] Fix failing test `test_momentum_positive_when_improving` — CI cannot pass with a failing test
- [ ] Add pytest/pytest-asyncio to requirements.txt — CI cannot install test runner without it

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI triggers on push/PR | R8.1 | Requires GitHub Actions infrastructure | Push to branch, verify workflow runs in Actions tab |
| Railway blocks deploy on failure | R8.2 | Requires Railway dashboard toggle | Push failing code, verify Railway skips deploy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
