# Phase 5: Injury Impact System - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Automatically fetch daily NHL injury reports, classify missing players by impact tier, and adjust win probabilities accordingly. Extend the existing manual `overrides.json` system to be data-driven. No WAR/GAR integration (deferred to future phase).

</domain>

<decisions>
## Implementation Decisions

### Player value tiers & impact sizing
- 3 tiers based on position and usage:
  - **Starting G:** ~3-5 pp adjustment (biggest single-player impact in hockey)
  - **Top-6 F / Top-4 D:** ~1.5-2.5 pp per player (core contributors)
  - **Bottom-6 F / Bottom-pair D:** ~0.5-1 pp per player (depth impact)
- Tier classification: use NHL API player stats (TOI/GP, points) to auto-classify
  - Top-6 F: rank by TOI among team forwards, top 6
  - Top-4 D: rank by TOI among team defensemen, top 4
  - Starting G: already resolved by Phase 4's goalie resolver
- Multiple injuries compound: sum individual penalties, cap at ~8pp total adjustment
- Impact is symmetrical: if both teams are equally depleted, adjustments cancel out

### Injury data source & freshness
- Primary: NHL API roster/injury endpoint (free, structured data)
- Injury statuses to track: IR (Injured Reserve), LTIR (Long-Term IR), Day-to-Day
- Refresh: once per pipeline run (same pattern as goalie confirmation)
- Cache injury data per game day — injuries rarely change intra-day
- Game-time decisions (GTD): treat as 50% likely out, apply half the adjustment
- No scraping needed — NHL API provides structured injury data

### Override coexistence
- Keep existing `overrides.json` system intact — manual overrides take priority over automated
- Automated injury adjustments apply AFTER manual overrides (additive, not replacing)
- If a manual override exists for a team AND automated injuries are detected, log both but manual wins on conflicts
- Never auto-write to overrides.json — keep automated and manual cleanly separated
- Existing override fields (`strength_penalty`, `expires`, `exclude`, `reason`) unchanged

### Dashboard display
- Show key injuries on game cards: "Key out: McDavid (IR), Nurse (DTD)" below team name
- Only show top-tier injuries (top-6 F, top-4 D, starting G) — don't clutter with depth players
- Show the total injury adjustment in the probability tooltip or details modal
- Flag when injury data significantly affects the model edge (>2pp swing)

### Claude's Discretion
- NHL API endpoint discovery for injury/roster data
- Exact TOI thresholds for tier classification
- How to handle mid-season trades (player moves team)
- Cache implementation details
- Test structure and synthetic injury scenarios
- Whether to add an `--injuries` CLI flag for standalone injury report

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `load_overrides()` at `app/core/service.py:213` — loads `~/.moneypuck/overrides.json` with expiry handling
- `apply_overrides()` at `app/core/service.py:256` — applies `strength_penalty` to team ratings
- `get_excluded_teams()` at `app/core/service.py:288` — excludes teams from betting
- `fetch_goalie_stats()` at `app/data/nhl_api.py:130` — NHL API fetching pattern to reuse
- `_fetch_with_retry()` in `app/data/data_sources.py` — retry pattern for external APIs
- Phase 4's `resolve_starter()` — goalie injury already partially handled

### Established Patterns
- Override format: `{"team_code": {"strength_penalty": -2.0, "reason": "McDavid IR", "expires": "2026-04-15"}}`
- Situational adjustments in `EdgeScoringAgent` — B2B, timezone already compound additively
- NHL API JSON parsing pattern from `nhl_api.py`
- 90s TTL cache pattern from Phase 1 for API responses

### Integration Points
- `EdgeScoringAgent.run()` in `app/core/agents.py` — applies sit_adj + goalie_adj + momentum_adj, injury_adj adds here
- `apply_overrides()` in `app/core/service.py` — injury adjustments layer alongside manual overrides
- `TrackerConfig` in `app/core/models.py` — may need injury impact multiplier config
- Dashboard game cards in `app/web/presentation.py` — injury display integration

</code_context>

<specifics>
## Specific Ideas

- R4.4 says "Manual override capability (existing overrides.json extended)" — keep manual as fallback, don't break existing workflow
- The user cares about the model correctly adjusting for star player absences — "Missing McDavid is treated same as full-health" is the problem statement
- Compound injuries matter: a team missing their #1C AND #1D should see a bigger penalty than just one

</specifics>

<deferred>
## Deferred Ideas

- Full WAR/GAR integration for precise player value — Phase 2 of injury system (noted in REQUIREMENTS.md out of scope)
- Historical injury data for backtesting impact — would require scraping past injury reports
- Injury trend analysis (frequently injured players) — future enhancement

</deferred>

---

*Phase: 05-injury-impact-system*
*Context gathered: 2026-03-07*
