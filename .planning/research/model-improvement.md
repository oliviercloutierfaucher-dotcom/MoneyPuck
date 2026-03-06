# Model Improvement & Validation Research

**Project:** MoneyPuck NHL Betting Edge Platform
**Researched:** 2026-03-06
**Overall confidence:** MEDIUM-HIGH

---

## 1. Brier Score Assessment: How Does 0.2430 Compare?

### The Honest Answer: Barely Above Random

A Brier score of 0.25 is the "no-skill" baseline for binary prediction (equivalent to predicting 50/50 for every game). Your Brier of 0.2430 beats this by only 0.007 -- that is a **2.8% skill improvement** over coin flipping.

**Benchmark context:**

| Model / Benchmark | Brier Score | Log Loss | Notes |
|-------------------|-------------|----------|-------|
| Coin flip (no skill) | 0.2500 | 0.6931 | Predict 50% every game |
| Home-ice only (predict 54% home) | ~0.2475 | ~0.6881 | Trivial baseline |
| Your model (current) | 0.2430 | -- | 2.8% above no-skill |
| Hockey-Statistics.com combined xG | -- | 0.6794 | Single-season test |
| MoneyPuck pre-game model | -- | 0.6580 | 2024-25, 60.4% favorite accuracy |
| Closing betting lines (market) | -- | ~0.6714 | The line to beat |
| Strong NHL model target | ~0.2250 | ~0.6600 | Estimated professional tier |
| Theoretical floor (NHL variance) | ~0.2100 | ~0.6400 | Diminishing returns below here |

**Confidence: HIGH** -- The 0.25 baseline is mathematical fact. MoneyPuck's published log loss of 0.658 is from their website.

### Key Insight

Your 60.1% win rate and 18.6% ROI backtest numbers are **more impressive than the Brier score suggests**, which means one of two things:
1. The model is good at identifying games where it has edge (selective accuracy) even though average calibration is mediocre -- this is actually what matters for betting
2. The backtester's synthetic odds generation may be inflating ROI (the market_base = 0.537 approach is a known limitation noted in the code)

**Recommendation:** Focus less on overall Brier score and more on **calibration in the tails** (when model says 60%+, does that side win 60%+ of the time?) and on **CLV tracking** against real closing lines.

---

## 2. Additional Signals That Improve NHL Win Probability

### Tier 1: High-Impact, Implementable Now

#### A. Confirmed Starting Goalie (Impact: 2-5 pp per game)

**Current gap:** `infer_likely_starter()` picks the season GP leader, which is wrong ~20-30% of the time (backup nights, injuries, tandem situations).

**Data sources:**
- **DailyFaceoff.com** `/starting-goalies` -- The gold standard. Updates throughout game day. Distinguishes "confirmed" vs "expected" vs "unconfirmed"
- **LeftWingLock.com** `/api/` -- Has a paid API endpoint specifically for starting goalies, line combinations
- **RotoWire** `/hockey/starting-goalies.php` -- Another reliable source

**Implementation approach:**
1. Scrape DailyFaceoff starting goalies page 2-3 hours before game time
2. Map goalie names to team codes
3. Look up that specific goalie's save%, GSAx, recent form (last 10 starts)
4. Fall back to GP-leader heuristic if scrape fails

**Timing considerations:** Some teams do not announce starters until warmups (~30 min before puck drop). For betting purposes, you want to place bets when DailyFaceoff shows "confirmed" or "expected" status, typically available by early afternoon on game day.

**Confidence: HIGH** -- DailyFaceoff and LeftWingLock are universally cited as the standard sources.

#### B. Injury Impact via WAR/GAR (Impact: 1-5 pp depending on player)

**Current gap:** Zero roster awareness. A team missing McDavid is treated identically to a fully healthy team.

**How professional models handle this:**
- Evolving Hockey's WAR model uses ridge regression (RAPM) to isolate individual player impact on expected goals for/against
- ~5.6 GAR = 1 WAR. A top-line player might generate 3-5 WAR per season
- Missing a 5-WAR player for a game removes roughly 0.06 WAR, which translates to ~1-3 pp of win probability depending on the opponent

**Implementation approach (recommended):**
1. Maintain a lookup table of player GAR/WAR values (from Evolving Hockey or computed from MoneyPuck player data)
2. Scrape daily injury reports (NHL API provides official injury lists)
3. For each team, sum the GAR of missing players
4. Convert missing GAR to a win probability adjustment: `adjustment = missing_gar_diff * scale_factor`
5. Reasonable scale_factor: 0.005-0.01 per GAR point (needs calibration)

**Simpler MVP approach:**
- Just track injuries to top-6 forwards and top-4 defensemen
- Apply a flat adjustment: -1.5 pp per missing top-6 forward, -1.0 pp per missing top-4 D
- This captures 80% of the value with 20% of the complexity

**Data sources for injuries:**
- NHL API: `https://api-web.nhle.com/v1/club-stats-season/{team}` and roster endpoints
- PuckPedia.com/injuries -- well-structured injury data
- DailyFaceoff.com also tracks lines and injuries

**Confidence: MEDIUM** -- The WAR/GAR framework is well-established. The specific pp-adjustment scale factors need empirical calibration on your model.

#### C. Schedule Density Beyond B2B (Impact: 1-2 pp cumulative)

**Current gap:** Only back-to-back detection. No 3-in-4, 4-in-6, or long road trip modeling.

**Research findings:**
- Back-to-back: 0.491 points% vs 0.565 with 1+ rest days (from rg.org analysis)
- 3-in-4 nights: additional ~1 pp penalty beyond individual B2B
- 4th-5th game of extended road trips show slight dip, then recovery
- Cross-timezone travel compounds fatigue effects

**Implementation:**
```python
def schedule_density_adjustment(team, game_date, games_rows):
    """Detect 3-in-4, 4-in-6, and long road trips."""
    games_last_4_days = count_games_in_window(team, game_date, days=4)
    games_last_6_days = count_games_in_window(team, game_date, days=6)
    consecutive_road = count_consecutive_road_games(team, game_date)

    adj = 0.0
    if games_last_4_days >= 3:  # 3-in-4
        adj -= 0.015
    elif games_last_6_days >= 4:  # 4-in-6
        adj -= 0.01
    if consecutive_road >= 4:  # long road trip fatigue
        adj -= 0.005
    return adj
```

**Confidence: MEDIUM** -- Directionally correct, specific magnitudes need validation.

### Tier 2: Moderate Impact, Worth Adding

#### D. Line Movement / Sharp Money Tracking (Impact: edge validation, not prediction)

**Current gap:** Model compares to current line only, ignoring opening line and movement direction.

**Why this matters for a betting product:**
- If your model says "home team 58%" and the line has moved FROM 55% TO 58%, you have NO edge -- the market already found what you found
- If the line moved FROM 58% TO 55% (moved against your model), that is a RED FLAG -- sharps disagree with you
- If the line opened at 52% and your model says 58%, that is real edge IF the line has not moved toward you yet

**Implementation:**
1. Record opening lines when they first appear (store in DB/file)
2. Track movement direction and magnitude over time
3. Add a "line movement agreement" signal to confidence scoring:
   - Line moved toward your prediction: confidence boost
   - Line moved away from your prediction: confidence penalty
   - Large unexplained movement: possible injury/news you missed

**CLV (Closing Line Value) as validation metric:**
- After each bet, record the closing line
- If you consistently beat the closing line, your model has genuine edge
- CLV is considered the single best predictor of long-term betting profitability

**Confidence: HIGH** (concept), **MEDIUM** (implementation details)

#### E. Momentum / Recent Form Refinement

**Current state:** You have composite_5g, composite_10g, and momentum (5g - 10g) with a 0.02 scaling factor.

**Improvement opportunities:**
- Weight recent goalie performance more heavily (goalie hot/cold streaks are real in NHL)
- Track power play/penalty kill trends separately (special teams form is more volatile)
- Consider goal differential in recent games, not just underlying metrics
- Score state: teams that have been winning by 2+ goals recently may be coasting in 3rd periods (inflating xGA)

**Confidence: MEDIUM** -- Momentum effects are real but noisy. Keep the 0.02 scaling factor conservative.

### Tier 3: Lower Priority / Harder to Implement

#### F. Player-Level Lineup Composition

The Hockey-Statistics.com model found that **forward individual goals** were the single best predictive variable (log loss 0.6817 vs 0.6931 baseline). Building player-level projections as MoneyPuck does (their model weights: 17% team ability, 54% scoring chances, 29% goaltending) would be a major leap but requires significantly more data infrastructure.

#### G. Travel Distance (Beyond Timezone)

Current model uses timezone difference. Actual travel distance matters less than timezone crossing (jet lag), so current approach captures most of the signal. Not worth additional complexity.

---

## 3. Model Validation: Gold Standard Practices

### Current Weakness: Single-Season Validation

Your model was tuned via grid search on **one season (2024-25)**. This is the single biggest risk in the entire system. Overfitting to one season's data means parameters may not generalize.

### What Professional Models Do

**1. Rolling Walk-Forward Validation (REQUIRED)**

Train on seasons 1..N, test on season N+1. Repeat across multiple seasons.

```
Train: 2019-20 to 2022-23 --> Test: 2023-24
Train: 2020-21 to 2023-24 --> Test: 2024-25
Train: 2021-22 to 2024-25 --> Test: 2025-26
```

This tests whether your parameters generalize across different eras (rule changes, COVID-era anomalies, talent shifts).

**Minimum:** 3 seasons of walk-forward testing. Gold standard: 5+ seasons.

**2. Out-of-Sample Parameter Stability**

Run grid search independently on each season. If optimal parameters cluster tightly (e.g., logistic_k always lands between 0.8-1.0), they are robust. If they vary wildly (logistic_k = 0.5 one year, 1.5 the next), the model is fitting noise.

**3. Calibration Curve Analysis**

Your backtester already computes calibration buckets. The key check: when you predict 60% home win probability, do those games result in ~60% home wins? The max calibration error metric (currently checked at <= 0.08 threshold) is a good start.

**4. Brier Skill Score (BSS)**

BSS = 1 - (Brier / Brier_baseline)

With Brier = 0.2430 and baseline = 0.25:
BSS = 1 - (0.2430 / 0.25) = 0.028 = 2.8% skill

Professional models target BSS > 5% (Brier < 0.2375). Top-tier models may hit BSS 8-12%.

**5. CLV Tracking (for betting validation)**

The ultimate validation for a betting model is not Brier score but Closing Line Value. If you consistently get better odds than the closing line, you have real edge regardless of short-term P&L variance.

**Confidence: HIGH** -- These are standard practices from both academic literature and professional betting.

---

## 4. Should You Add Advanced ML (XGBoost, Neural Nets)?

### Verdict: Add XGBoost for the xG-to-Win Probability Step, Keep Logistic for Ensemble

**Current architecture:**
MoneyPuck metrics --> Z-score --> Logistic regression --> Win probability

**The ceiling problem:**
Your logistic model maps a single "composite strength difference" to win probability. This is a **linear combination of features fed into a sigmoid**. It cannot capture:
- Non-linear interactions (e.g., a team with elite goaltending AND bad offense performs differently than the linear combination suggests)
- Feature interactions (e.g., high PP% only matters when opponent takes many penalties)
- Threshold effects (e.g., save% below 0.895 is catastrophic, above 0.920 has diminishing returns)

**XGBoost advantages for this problem:**
- Handles non-linear relationships automatically
- Feature interactions discovered during training
- Robust to feature scaling (no z-scoring needed)
- Fast training and inference
- MoneyPuck itself uses gradient boosting for their xG model
- Evolving Hockey's game projection model uses similar approaches

**What NOT to do:**
- **Don't use neural networks.** You have ~1,300 games/season. That is far too little data for deep learning. XGBoost/LightGBM are strictly better for tabular data at this scale.
- **Don't replace the ensemble approach.** Keep Elo as a separate signal and blend with the ML model. Ensemble diversity improves robustness.

**Recommended architecture:**

```
Current:
  16 metrics --> Z-score --> weighted sum --> logistic(diff) --> prob

Improved:
  16 metrics + goalie stats + situational + injury
      |
      v
  XGBoost (trained on 3+ seasons walk-forward)
      |
      v
  xgb_prob (0-1)
      |
  Ensemble: 0.60 * xgb_prob + 0.15 * elo_prob + 0.25 * logistic_prob
      |
      v
  final_prob
```

Why keep logistic in the ensemble? It provides a strong regularizing signal. If XGBoost overfit on a particular season, the logistic model pulls it back toward sensible values. This is exactly what FiveThirtyEight does -- they use simple Elo as a "prior" even when they have more complex models.

**Expected improvement:** Moving from pure logistic to XGBoost ensemble could improve Brier score by 0.005-0.015 (bringing it to ~0.228-0.238 range), based on comparable improvements seen in hockey analytics literature.

**Confidence: MEDIUM-HIGH** -- XGBoost superiority over logistic regression for tabular sports prediction is well-established. The specific improvement magnitude is estimated.

---

## 5. How Professional NHL Sites Model Win Probability

### MoneyPuck (moneypuck.com)

**Algorithm:** Gradient boosting
**Training data:** 2017-18 through 2023-24 seasons, rebuilt January 2025
**Model components (weighted):**
- Team ability to win: 17%
- Scoring chances quality: 54%
- Goaltending quality: 29%

**Features:** 15 variables for xG (shot distance, angle, type, rebound characteristics, man advantage, etc.), plus rest differential and home/away
**Performance:** 60.4% favorite accuracy, 0.658 log loss (2024-25 season)
**Starting goalie prediction:** Separate 10-variable model (rest days, recent workload, save%, GSAx, age, game importance)
**Season simulation:** 100,000 Monte Carlo simulations for playoff odds

**Key takeaway:** MoneyPuck's model is **substantially more sophisticated** than your current approach, but achieves only ~60% accuracy -- remarkably close to your 60.1%. This suggests you are near the accuracy ceiling for pre-game NHL prediction.

### Evolving Hockey (evolving-hockey.com)

**Algorithm:** Ridge regression (RAPM) for player-level impact
**Key innovation:** Player-level WAR/GAR decomposition, then roster-based game projections
**Features:** Even-strength xG impact, PP offense, PK defense, all isolated per player via RAPM
**Use case:** Their model is lineup-dependent -- it accounts for WHO is playing, not just team averages

### FiveThirtyEight (historical, now defunct)

**Algorithm:** Pure Elo with adjustments
**K-factor:** 6
**Home advantage:** 50 Elo points (~57% win probability for equal teams)
**Season regression:** 30% toward 1505 (your model uses 50% toward 1505)
**Key differences from your Elo:**
- 538 regresses 30%, you regress 50%. 30% may be better -- it means prior-season performance carries more weight
- 538's home advantage of 50 Elo points maps to ~57%, which seems too high for modern NHL (~54-55%). Your 50 points is the same value.

### Natural Stat Trick (naturalstattrick.com)

**Focus:** xG model for shot quality, not game prediction
**Algorithm:** Not publicly disclosed, trained on Fenwick shots from 2007+
**Features:** Shot type, location, angle, time since last event, rebound context

### Hockey-Statistics.com Game Projection Model

**Most relevant to your use case.** Their variable importance analysis found:
1. Forward individual goals (log loss 0.6817)
2. Forward on-ice goals (0.6819)
3. Forward xGF (0.6820)
4. **Key finding:** Player-level forward offensive stats outperform team-level metrics

**Implication for your model:** Your model uses only team-level aggregates. Adding the top-6 forward xGF metric (even as a team average) could improve discrimination.

**Confidence: HIGH** -- All methodology details are from official published sources.

---

## 6. Injury Impact Quantification: Best Approach

### Recommended: Tiered Injury System

**Tier 1 (MVP -- implement first):**
Flat adjustments by roster position, applied as win probability deltas.

```python
INJURY_IMPACT = {
    "1C": -0.025,   # Top-line center (McDavid, Matthews)
    "1LW": -0.015,  # Top-line winger
    "1RW": -0.015,
    "2C": -0.012,
    "2LW": -0.008,
    "2RW": -0.008,
    "3C": -0.005,
    "3LW": -0.003,
    "3RW": -0.003,
    "1D": -0.012,   # Top-pair D
    "2D": -0.010,
    "3D": -0.008,
    "4D": -0.005,
    "G1": -0.030,   # Starting goalie (handled separately by goalie model)
}
```

Total impact: team missing two top-6 forwards loses ~3-4 pp. This is consistent with WAR-based estimates.

**Tier 2 (better, but more work):**
Use Evolving Hockey's GAR data (or compute your own from MoneyPuck player stats) to assign per-player impact values. Sum missing player GAR and convert to probability adjustment.

**Tier 3 (professional grade):**
Build a lineup-composition model like Evolving Hockey -- project ice time redistribution when a player is injured, and model the cascading lineup effects (e.g., losing your 1C means your 2C faces tougher matchups).

**Data source for daily injury tracking:**
The NHL API provides roster and injury information. DailyFaceoff.com tracks line combinations that implicitly reveal injured/scratched players.

**Confidence: MEDIUM** -- The tier system is sound. Specific pp values are estimates that need empirical calibration via backtesting with historical injury data.

---

## 7. Goalie Starter Confirmation: Timing and Sources

### Current Problem

`infer_likely_starter()` uses season GP leader. This fails for:
- Backup starts (~25-35% of games per team)
- Injured starters (still selected until backup surpasses in GP)
- Tandem situations (DAL, NYR at times)
- Platoon goalies later in season

### Recommended Data Pipeline

```
Morning (10 AM ET):
  1. Scrape DailyFaceoff.com/starting-goalies
  2. Parse status: "Confirmed" / "Expected" / "Unconfirmed"
  3. For "Confirmed": use that goalie's stats directly
  4. For "Expected": use that goalie's stats but reduce confidence by 10%
  5. For "Unconfirmed": fall back to weighted average of both goalies

Afternoon (2-4 PM ET):
  6. Re-scrape for updates (many confirmations come by early afternoon)
  7. Re-run model with updated goalie info

Pre-game (30 min before puck drop):
  8. Final confirmation from warmup reports
  9. If bet not yet placed, use final confirmed starter
```

### Alternative: LeftWingLock API

LeftWingLock offers a paid API (`leftwinglock.com/api/`) that provides:
- Starting goalie confirmations
- Line combinations
- Deployment data

Cost is reasonable for a commercial product. This is the cleanest integration path.

### Goalie Performance Features to Track

Beyond season save%, use:
- **Last 10 starts save%** (recent form, more predictive than season average)
- **Goals Saved Above Expected (GSAx)** -- controls for shot quality faced
- **Home/away splits** (some goalies perform very differently by venue)
- **Save% vs opponent** (small sample but captures matchup effects)
- **Days since last start** (rust factor: goalies with 5+ days off perform slightly worse)

**Confidence: HIGH** -- DailyFaceoff is the universally cited gold standard for goalie confirmations.

---

## 8. Accuracy Ceiling for NHL Pre-Game Prediction

### The Hard Truth About NHL Parity

The NHL is the **most random** of the four major North American sports for game-level prediction. Reasons:
- Goaltending variance is enormous (a backup having a great night swings outcomes)
- Small sample of goals per game (2-3 per team) means high outcome variance
- Puck luck (shot deflections, bounces) is a larger factor than in basketball or baseball
- Salary cap creates competitive balance

### Observed Accuracy Ranges

| Model Type | Favorite Win Rate | Notes |
|------------|-------------------|-------|
| Home team always wins | ~54% | Trivial |
| Elo-only models | ~57-58% | FiveThirtyEight |
| MoneyPuck (sophisticated) | 60.4% | 2024-25 season |
| Your model | 60.1% | 2024-25 season |
| Betting market (closing line) | ~60-62% | Historically best |
| Theoretical ceiling | ~63-65% | Diminishing returns |

**Your model at 60.1% is already in the professional range.** The gap between you and the market (~2 pp) is where the money is, but closing that gap requires the improvements listed above.

### Where Additional ML Helps

Moving from logistic to XGBoost will NOT dramatically change favorite-win accuracy (maybe 60.1% to 60.5-61%). The value is in **better calibration** -- when the model says 65%, it should win 65% of the time, not 60%. Better calibration = better Kelly sizing = better ROI.

**Confidence: HIGH** -- MoneyPuck's published 60.4% and the general 63-65% ceiling are consistent across multiple independent sources.

---

## 9. Priority-Ranked Implementation Roadmap

### Phase 1: Validation Infrastructure (CRITICAL)

**Why first:** You cannot evaluate improvements without proper validation.

1. Multi-season backtesting (load 3-5 seasons of MoneyPuck data)
2. Walk-forward validation framework
3. Parameter stability analysis across seasons
4. CLV tracking against real closing lines

### Phase 2: Confirmed Starting Goalies

**Why second:** Highest single-feature impact (2-5 pp per game when current model has wrong goalie).

1. DailyFaceoff scraper
2. Goalie-specific performance features (recent form, GSAx)
3. Confidence adjustment based on confirmation status

### Phase 3: Injury Impact

**Why third:** Second-highest impact, especially for games involving star players.

1. Flat-adjustment tier system (MVP)
2. NHL API injury data integration
3. Backtest calibration of adjustment magnitudes

### Phase 4: XGBoost Win Probability

**Why fourth:** Better calibration and non-linear feature interactions, but requires solid validation infrastructure first.

1. Feature engineering (all current metrics + goalie + injuries + situational)
2. XGBoost model with walk-forward training
3. Ensemble with existing logistic and Elo models
4. Calibration comparison

### Phase 5: Schedule Density & Line Movement

**Why last:** Lower individual impact, but adds polish.

1. 3-in-4, 4-in-6, long road trip detection
2. Opening line recording and movement tracking
3. CLV computation and reporting

---

## 10. Sources

### Official Model Documentation
- [MoneyPuck About & Methodology](https://moneypuck.com/about.htm)
- [FiveThirtyEight NHL Methodology](https://fivethirtyeight.com/methodology/how-our-nhl-predictions-work/)
- [Evolving Hockey Overview](https://evolving-hockey.com/evolving-hockey-overview/)
- [Corsica Predictions Explained](https://www.corsicahockey.com/corsica-predictions-explained)

### Research & Analysis
- [Hockey-Statistics.com Game Projection Variables Part I](https://hockey-statistics.com/2022/01/03/game-projection-model-the-variables-part-i/)
- [Hockey-Statistics.com Variables Part IB](https://hockey-statistics.com/2022/01/12/game-projection-model-the-variables-part-ib/)
- [Evolving Hockey xG Model](https://evolving-hockey.com/blog/a-new-expected-goals-model-for-predicting-goals-in-the-nhl/)
- [Hockey Graphs: GAR for Injury Impact](https://hockey-graphs.com/2017/04/21/fqg-using-goals-above-replacement-to-measure-injury-impact/)
- [Comparison of Four Public xG Models](https://hockeyanalysis.com/2024/04/08/quick-comparison-of-four-public-expected-goal-models/)
- [NHL Schedule Factors Impact](https://rg.org/research/sports-data-analysis/how-nhl-schedule-factors-impact-team-performance)
- [Schedule Density and Injuries (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8058808/)

### Betting & Validation
- [CLV Explained (VSiN)](https://vsin.com/how-to-bet/the-importance-of-closing-line-value/)
- [Brier Score (Wikipedia)](https://en.wikipedia.org/wiki/Brier_score)
- [AI Model Calibration for Sports Betting](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score)

### Data Sources for Goalie Confirmation
- [DailyFaceoff Starting Goalies](https://www.dailyfaceoff.com/starting-goalies)
- [LeftWingLock API](https://leftwinglock.com/api/)
- [RotoWire Starting Goalies](https://www.rotowire.com/hockey/starting-goalies.php)

### ML Approach References
- [XGBoost NHL xG Model (GitHub)](https://github.com/Nick-Glass/Hockey-XG-Model)
- [ML Outperforms Logistic Regression for NHL (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7522848/)
- [Systematic Review of ML in Sports Betting](https://arxiv.org/html/2410.21484v1)
