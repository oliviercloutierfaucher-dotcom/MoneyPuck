---
phase: 7
slug: dashboard-rebuild
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pytest discovery (no explicit config) |
| **Quick run command** | `python -m pytest tests/web/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/web/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | R5.3, R5.5 | integration | `pytest tests/web/test_partials.py -x` | Wave 0 | pending |
| 07-01-02 | 01 | 1 | R5.3 | integration | `pytest tests/web/test_tab_routes.py -x` | Wave 0 | pending |
| 07-02-01 | 02 | 2 | R5.4, R5.6 | smoke | `pytest tests/web/test_app.py -x` | existing | pending |
| 07-02-02 | 02 | 2 | R5.7 | unit | `pytest tests/web/test_partials.py -x -k "poll"` | Wave 0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/web/test_partials.py` — tests for all 5 partial endpoints (HX-Request header, HTML fragment response)
- [ ] `tests/web/test_tab_routes.py` — tests for full page routes returning base.html with correct active tab
- [ ] Tests must use FastAPI TestClient (no live server needed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual rendering quality | R5.4 | Visual verification needed | Start server, check cards/layout/theme in browser |
| Mobile responsiveness | R5.6 | Requires visual viewport testing | Check at 375px, 768px, 1024px in browser dev tools |
| HTMX tab switching UX | R5.5 | Interaction verification | Click tabs, verify smooth content swap with no flash |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 25s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
