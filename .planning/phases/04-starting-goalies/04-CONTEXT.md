# Phase 4: Starting Goalies - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the GP-leader heuristic (`infer_likely_starter()`) with confirmed starting goalie data. Use the actual starter's save%/GSAx instead of always picking the season GP leader. Graceful fallback to GP-leader when no confirmation is available.

</domain>

<decisions>
## Implementation Decisions

### Data source
- Primary: NHL API `/gamecenter/{gameId}/landing` endpoint — free, no scraping, includes confirmed starters ~1-2 hours before puck drop
- Secondary fallback: DailyFaceoff confirmed starters page (scrape) — available earlier in the day (by ~noon ET)
- Try NHL API first; if starter not yet confirmed, try DailyFaceoff; if neither available, fall back to GP-leader heuristic
- No paid data feeds — keep it free

### Timing & freshness
- Confirmed starters typically available by early afternoon on game days (R3.4)
- Cache confirmed starter data per game day (don't re-fetch within same pipeline run)
- Dashboard auto-refresh should pick up new confirmations as they become available
- No special scheduling needed — just fetch when pipeline runs

### Fallback behavior
- 3-tier fallback: confirmed starter → DailyFaceoff → GP-leader heuristic (existing `infer_likely_starter()`)
- When using GP-leader fallback, flag the prediction as "unconfirmed starter" in output
- Never skip the goalie adjustment entirely — GP-leader is better than nothing
- Fallback follows Phase 3 pattern: graceful degradation, don't crash

### Backtest impact validation
- Historical confirmed starter data is NOT available for past seasons — can't backtest with real confirmations
- Instead: validate by simulating the impact — compare model output with correct starter vs wrong starter on known backup-start games
- Use 2024-25 season games where backup started (identifiable from game logs) to measure the error introduced by GP-leader heuristic
- Success: demonstrate that correct goalie identification improves Brier score by >0.005 on those games
- COVID season excluded from this validation (goalie rotations were abnormal)

### Claude's Discretion
- NHL API endpoint discovery and parsing details
- DailyFaceoff scraping implementation (CSS selectors, etc.)
- Caching strategy (in-memory dict with TTL vs file-based)
- How to identify backup-start games in historical data for validation
- Whether to add GSAx alongside save% or just improve save% accuracy
- Test structure and synthetic data design

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `infer_likely_starter()` at `app/data/nhl_api.py:213` — current GP-leader heuristic, returns `{save_pct, gaa, games_played, ...}`. This becomes the fallback.
- `fetch_goalie_stats()` at `app/data/nhl_api.py:130` — fetches season goalie stats from NHL API. Already has the data format we need.
- `goalie_matchup_adjustment()` at `app/math/math_utils.py:355` — consumes `starter_save_pct`, applies `goalie_impact=1.5` multiplier. No changes needed here — just feed it better data.
- `TeamMetrics.starter_save_pct` / `starter_gaa` fields already exist in `app/core/models.py:46-47`

### Established Patterns
- NHL API fetching with `_fetch_with_retry()` in `app/data/data_sources.py` — retry pattern for external APIs
- `fetch_goalie_stats()` already parses NHL API JSON — same pattern extends to gamecenter endpoint
- Graceful fallback pattern from Phase 3 (404 → skip, don't crash)
- Odds API 90s TTL cache pattern from Phase 1 — same approach works for goalie confirmations

### Integration Points
- `MoneyPuckAgent.run()` in `app/core/agents.py:188-194` — builds `goalie_lookup` dict, calls `infer_likely_starter()`. This is where confirmed starter data replaces the heuristic.
- `TrackerConfig.goalie_impact` at `app/core/models.py:88` — multiplier stays the same, input data improves
- Pipeline orchestration in `app/core/service.py` — may need to pass game IDs for gamecenter lookups

</code_context>

<specifics>
## Specific Ideas

- The code itself documents this as a known limitation with a clear improvement path (nhl_api.py:234-236)
- R3.2: Use confirmed goalie's ACTUAL save%/GSAx — not just confirm who starts, but use their real stats
- R3.3: Graceful fallback is critical — model should never be worse than current GP-leader approach
- The user cares about model accuracy improvement, not the data source implementation details

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-starting-goalies*
*Context gathered: 2026-03-07*
