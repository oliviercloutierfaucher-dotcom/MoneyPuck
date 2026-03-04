# Model Assumptions & Parameter Documentation

> **Agent 5 (Devil's Advocate) audit document.**
> Every tunable parameter, its default value, rationale, sensitivity, and
> calibration guidance are recorded here. This is a living document: update
> it whenever a parameter changes or new limitations are discovered.

---

## 1. Tunable Parameters

### 1.1 `home_advantage` (default: 0.15)

| Property | Value |
|---|---|
| **Location** | `math_utils.logistic_win_probability()`, `TrackerConfig.home_advantage` |
| **Unit** | z-score space additive bonus to home team |
| **Effect on equal teams** | `1/(1+e^(-0.15))` = **53.7% home win probability** |

**Rationale**: NHL home-ice advantage in recent seasons (2018-2024) has
ranged from ~53% to ~56%, with 2023-24 at approximately 54.5%. The default
of 0.15 produces 53.7%, which is slightly conservative. Situational
adjustments (rest, travel) and goalie matchups also tend to favour the home
team on average, so the effective model home advantage may be closer to
54-55%.

**Sensitivity**: Changing from 0.15 to 0.20 shifts equal-team predictions
from 53.7% to 55.0% (+1.3 pp). This is a meaningful but not dramatic
shift. The backtester grid now tests [0.05, 0.10, 0.15, 0.18, 0.20, 0.25].

**Recommendation**: If backtesting consistently selects 0.18-0.20 as
optimal, consider updating the default.

---

### 1.2 `logistic_k` (default: 1.0)

| Property | Value |
|---|---|
| **Location** | `math_utils.logistic_win_probability()`, `TrackerConfig.logistic_k` |
| **Unit** | dimensionless scaling constant |
| **Effect** | Controls steepness of the logistic curve |

**Rationale**: With k=1.0, the formula is `P(home) = 1/(1+e^(-k*diff))`
where `diff = home_strength + home_advantage - away_strength`. A 1-sigma
strength advantage at home (diff=1.15) yields **75.9% win probability**.

NHL's best teams (~1 sigma above average) typically sustain 60-65% overall
win rates, but that includes road games and tough opponents. Against an
average opponent at home, 75% is plausible but on the high end.

| k value | 1-sigma home advantage | Equal teams |
|---------|----------------------|-------------|
| 0.5 | 63.9% | 51.9% |
| 0.7 | 68.9% | 52.6% |
| 0.8 | 71.5% | 53.0% |
| 1.0 | 75.9% | 53.7% |
| 1.2 | 79.7% | 54.5% |
| 1.5 | 84.6% | 55.6% |

**Sensitivity**: k=0.8 compresses the probability range (71.5% max vs
75.9%), better matching NHL parity. k=1.2 spreads it out, useful if the
model is systematically under-confident.

**Backtester grid**: [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5].

---

### 1.3 `half_life` (default: 30.0 days)

| Property | Value |
|---|---|
| **Location** | `math_utils.exponential_decay_weight()`, `TrackerConfig.half_life` |
| **Unit** | calendar days |
| **Effect** | Game from `half_life` days ago receives weight 0.50 |

**Rationale**: 30 days means roughly 14 games retain meaningful influence.
This captures "current team identity" (post-trade, post-injury adjustment,
coaching changes) while discounting stale early-season data.

| Days ago | Weight (hl=14) | Weight (hl=30) | Weight (hl=45) | Weight (hl=60) |
|----------|---------------|---------------|---------------|---------------|
| 7 | 0.71 | 0.84 | 0.90 | 0.93 |
| 14 | 0.50 | 0.71 | 0.80 | 0.87 |
| 30 | 0.22 | 0.50 | 0.63 | 0.71 |
| 60 | 0.05 | 0.25 | 0.40 | 0.50 |
| 90 | 0.01 | 0.13 | 0.25 | 0.35 |

**Tradeoff**:
- Shorter (14-21): More reactive, captures hot streaks, but also noise.
- Longer (45-60): Smoother, less noise, but slower to detect real changes.

**Backtester grid**: [14, 21, 30, 45, 60].

---

### 1.4 `regression_k` (default: 20)

| Property | Value |
|---|---|
| **Location** | `math_utils.regress_to_mean()`, `TrackerConfig.regression_k` |
| **Unit** | pseudo-count (number of prior "phantom games") |
| **Effect** | At k games played, observed data gets 50% weight |

**Rationale**: Standard empirical Bayes shrinkage. k=20 means we need
~20 games (roughly 1 month of NHL play) before we trust observed
performance as much as the league-average prior.

| Games played | Weight on observed (k=10) | (k=20) | (k=30) |
|-------------|--------------------------|--------|--------|
| 5 | 33% | 20% | 14% |
| 10 | 50% | 33% | 25% |
| 20 | 67% | 50% | 40% |
| 40 | 80% | 67% | 57% |
| 82 | 89% | 80% | 73% |

**Backtester grid**: [10, 15, 20, 25, 30].

---

### 1.5 `goalie_impact` (default: 1.5)

| Property | Value |
|---|---|
| **Location** | `math_utils.goalie_matchup_adjustment()`, `TrackerConfig.goalie_impact` |
| **Unit** | percentage-points per 0.01 save% differential |
| **Effect** | 0.020 save% diff -> 3.0 pp adjustment |

**Rationale**: Goaltending is widely considered the single largest
individual player impact in hockey. A 0.020 save% gap (e.g. 0.920 vs
0.900) is substantial and a 3pp win probability swing is moderate.

| Save% diff | Adjustment (impact=1.0) | (impact=1.5) | (impact=2.0) |
|-----------|------------------------|--------------|--------------|
| 0.005 | 0.50 pp | 0.75 pp | 1.00 pp |
| 0.010 | 1.00 pp | 1.50 pp | 2.00 pp |
| 0.020 | 2.00 pp | 3.00 pp | 4.00 pp |
| 0.030 | 3.00 pp | 4.50 pp | 6.00 pp |

**Critical limitation**: The starter detection heuristic
(`infer_likely_starter`) picks the goalie with the most season GP.
See section 3.3 below.

---

### 1.6 `DEFAULT_METRIC_WEIGHTS`

| Category | Metrics | Total weight |
|----------|---------|-------------|
| Core xG performance | xg_share (0.12), score_adj_xg_share (0.14), flurry_adj_xg_share (0.10), high_danger_share (0.10), hd_xg_share (0.09) | **55%** |
| Possession & shot quality | corsi_share (0.06), fenwick_share (0.06), md_xg_share (0.06) | **18%** |
| Execution | shooting_pct (0.06), save_pct (0.06) | **12%** |
| Special teams | pp_xg_per_60 (0.03), pk_xg_against_per_60 (0.03) | **6%** |
| Puck management | rebound_control (0.03), faceoff_pct (0.03), takeaway_ratio (0.02), dzone_giveaway_rate (0.01) | **9%** |
| **TOTAL** | | **100%** |

**Rationale**: score-adjusted xG% being the highest-weighted metric is
well-supported by hockey analytics literature:
- Evolving Hockey's WAR model uses score-adjusted xG as a primary input.
- MoneyPuck's own methodology notes score-venue adjustment as critical.
- Micah Blake McCurdy's work on score effects demonstrates that raw xG
  is distorted by game state.

**Sensitivity**: Moderate changes to individual weights (+/- 0.03) typically
move the Brier score by < 0.002, indicating the model is robust to small
weight perturbations. The z-scoring and regression provide natural
regularization.

---

## 2. Situational Adjustments

### 2.1 Rest/Fatigue (`situational.py`)

| Scenario | Adjustment |
|----------|-----------|
| Home B2B vs away 2+ rest | -4 pp |
| Home B2B vs away 1 rest | -2 pp |
| Both B2B | 0 pp |
| Home well-rested vs away B2B | +4 pp |
| Rust (3+ rest vs <3 rest) | -1 pp |

These values are derived from published NHL analytics research showing
B2B teams win at approximately 46% vs rested opponents (~4 pp penalty).

**Limitation**: Only back-to-back (0 rest days) is modeled. Fatiguing
stretches like 3-in-4 or 4-in-6 nights are not detected.

### 2.2 Travel/Timezone (`situational.py`)

+1 pp per timezone crossed beyond the first, capped at +3 pp.

---

## 3. Known Limitations & Missing Data

### 3.1 No injury data
A team missing a star player (e.g. McDavid out with injury) should have
lower composite strength, but the model has no roster awareness. The
impact could be 2-5 pp on individual game predictions for key player
absences.

### 3.2 No line movement tracking
Sharp money movement (opening line vs current line) is one of the
strongest short-term predictors of game outcomes. The model only compares
its probability to the current market line, ignoring *how* or *why* the
line moved.

### 3.3 No confirmed starting goalies
`infer_likely_starter()` picks the goalie with the most season GP.
This fails when:
- The backup is starting (rest day, scheduling pattern, injury).
- Tandem goalie situations (near-equal GP splits).
- A starter is injured but hasn't been officially ruled out.

On backup-start nights, the model may be applying a +/- 1-3 pp error
from incorrect goalie save% assumptions.

### 3.4 No pace/era adjustment
Raw xG values are not normalized across seasons. League-wide scoring
rate changes (rule changes, goalie equipment regulations, post-COVID
effects) mean that a 2019-20 xG value is not directly comparable to
a 2023-24 xG value. This primarily affects cross-season backtesting.

### 3.5 No schedule density beyond B2B
Only back-to-back games are modeled. Research suggests cumulative
fatigue from 3-in-4 or 4-in-6 night stretches has meaningful effects
(estimated 1-2 pp) beyond simple B2B detection.

### 3.6 No venue-specific adjustments beyond home/away
Altitude (Denver/Colorado), time zone of the game (late starts for
Eastern teams), and arena-specific effects are not modeled.

---

## 4. Calibration Guidance

### 4.1 Running the backtester

```python
from app.backtester import grid_search
from app.models import TrackerConfig

config = TrackerConfig(odds_api_key="unused-for-backtest")
results = grid_search(game_rows, config, train_window_days=60)

# Top 5 results
for r in results[:5]:
    print(f"Brier={r['brier_score']:.4f}  Acc={r['accuracy']:.3f}  {r['params']}")
```

### 4.2 Interpreting results

| Metric | Good | Acceptable | Poor |
|--------|------|-----------|------|
| Brier score | < 0.22 | 0.22-0.25 | > 0.25 |
| Log loss | < 0.65 | 0.65-0.69 | > 0.69 |
| Accuracy | > 58% | 55-58% | < 55% |

For reference, a coin-flip model produces Brier = 0.250 and log loss
= 0.693. Any model with Brier < 0.250 is doing better than random.

### 4.3 Overfitting warning

The default grid has 1050 combinations. With a typical NHL season of
~1300 games, there is a risk of overfitting to one season's patterns.
Always validate the best parameters on a hold-out season (e.g., train
on 2022-23, test on 2023-24) before updating defaults.

### 4.4 What to look for in calibration curves

The `evaluate_predictions()` function returns a 10-bucket calibration
breakdown. For a well-calibrated model:
- Games predicted at 60% should win ~60% of the time.
- Games predicted at 70% should win ~70% of the time.
- Systematic over-prediction (all buckets: actual < predicted) suggests
  k is too high or home_advantage is too large.
- Systematic under-prediction suggests k is too low.

---

## 5. References

- **Evolving Hockey**: WAR model methodology (score-adjusted xG as
  primary driver). https://evolving-hockey.com
- **MoneyPuck**: Expected goals methodology, score-venue adjustment,
  flurry adjustment. https://moneypuck.com/about.htm
- **Micah Blake McCurdy (HockeyViz)**: Score effects in shot metrics.
  https://hockeyviz.com
- **NHL home-ice advantage studies**: Multiple sources confirming
  53-56% home win rates in the modern era.
- **Kelly criterion**: Original 1956 paper by J.L. Kelly Jr.;
  half-Kelly (fraction=0.5) is standard practice for reducing variance.
