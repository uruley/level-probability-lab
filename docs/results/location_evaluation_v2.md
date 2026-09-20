# Location distance bands v2 - development results

**The broader bands do not show a dependable positive location advantage in the primary five-minute, 1:1 comparison.** Hourly moving averages have usable coverage, but nearby groups do not beat the matched fair-coin direction control with a positive 95% interval. Daily-level and confluence groups remain sparse.

This is post-hoc development on the same May/June data already examined in v1. It is not new independent validation. All bands were specified and their counts saved before v2 outcomes were joined; no thresholds were selected from these scores.

## Scope

- 2,214 immutable Base forecasts, 41 sessions; 13,284 inherited outcome rows across 1:1/2:1/3:1 and five-minute/extended windows.
- Five separate families; disjoint 0-0.5R, >0.5-1R, >1-2R, >2R and unknown bands within each family.
- R is the existing one-minute ATR14 risk distance, not an hourly or daily ATR.
- Context and outcome ledgers were reused, hash-checked and left unchanged. No retraining, new inference, downloads, live feed or July access.
- Confluence distance is the smallest radius that contains price and a pair of hourly/daily SMAs, including the distance between the pair; <=0.5R reproduces v1.

## Primary results: five minutes, 1:1

Percentages include all completed outcomes: target, stop, neither and ambiguous. The control is the exact average of up/down outcomes at each matched origin, not an assumed 50% success rate.

| Family | Distance | Forecasts / sessions | Kronos target first | Fair coin | Excess (95% interval) | Coverage flag |
|---|---|---|---|---|---|---|
| Hourly moving averages | 0-0.5R | 191 / 34 | 42.4% | 43.5% | -1.0 pp [-6.7, +4.6] pp | Adequate |
| Hourly moving averages | >0.5-1R | 173 / 35 | 43.9% | 43.1% | +0.9 pp [-5.5, +7.5] pp | Adequate |
| Hourly moving averages | >1-2R | 280 / 36 | 38.2% | 42.5% | -4.3 pp [-10.4, +0.9] pp | Adequate |
| Hourly moving averages | >2R | 1570 / 41 | 45.7% | 43.5% | +2.1 pp [-0.1, +4.3] pp | Adequate |
| Daily moving averages | 0-0.5R | 49 / 12 | 36.7% | 38.8% | -2.0 pp [-13.6, +8.2] pp | Sparse |
| Daily moving averages | >0.5-1R | 43 / 11 | 46.5% | 44.2% | +2.3 pp [-6.7, +14.3] pp | Sparse |
| Daily moving averages | >1-2R | 80 / 13 | 43.8% | 45.0% | -1.2 pp [-10.3, +12.9] pp | Sparse |
| Daily moving averages | >2R | 2042 / 41 | 44.5% | 43.4% | +1.1 pp [-0.8, +2.8] pp | Adequate |
| Hourly Bollinger boundaries | 0-0.5R | 42 / 14 | 47.6% | 40.5% | +7.1 pp [-5.6, +19.0] pp | Sparse |
| Hourly Bollinger boundaries | >0.5-1R | 30 / 11 | 46.7% | 43.3% | +3.3 pp [-13.2, +18.2] pp | Sparse |
| Hourly Bollinger boundaries | >1-2R | 94 / 22 | 34.0% | 44.1% | -10.1 pp [-16.8, -2.3] pp | Sparse |
| Hourly Bollinger boundaries | >2R | 2048 / 41 | 44.7% | 43.4% | +1.3 pp [-0.7, +3.1] pp | Adequate |
| Daily Bollinger boundaries | 0-0.5R | 16 / 6 | 62.5% | 46.9% | +15.6 pp [-15.8, +35.9] pp | Sparse |
| Daily Bollinger boundaries | >0.5-1R | 14 / 6 | 35.7% | 39.3% | -3.6 pp [-34.6, +40.0] pp | Sparse |
| Daily Bollinger boundaries | >1-2R | 36 / 7 | 47.2% | 45.8% | +1.4 pp [-13.9, +13.2] pp | Sparse |
| Daily Bollinger boundaries | >2R | 2148 / 41 | 44.2% | 43.3% | +0.9 pp [-1.1, +2.7] pp | Adequate |
| Hourly/daily SMA confluence | 0-0.5R | 5 / 2 | 80.0% | 40.0% | +40.0 pp unavailable | Sparse |
| Hourly/daily SMA confluence | >0.5-1R | 20 / 5 | 25.0% | 40.0% | -15.0 pp [-35.7, -7.1] pp | Sparse |
| Hourly/daily SMA confluence | >1-2R | 45 / 9 | 35.6% | 37.8% | -2.2 pp [-17.2, +28.3] pp | Sparse |
| Hourly/daily SMA confluence | >2R | 2144 / 41 | 44.6% | 43.5% | +1.1 pp [-0.9, +2.9] pp | Adequate |

Coverage flag requires >=100 pooled origins across >=10 sessions, and >=30 origins across >=5 sessions in EACH month. It describes sample coverage only, not statistical power or confirmation. All unknown bins have zero origins and are retained in the machine-readable files.

## Hourly averages: month-to-month check

| Distance | May: Kronos / fair coin (N) | June: Kronos / fair coin (N) |
|---|---|---|
| 0-0.5R | 43.2% / 43.9% (74) | 41.9% / 43.2% (117) |
| >0.5-1R | 40.6% / 43.5% (69) | 46.2% / 42.8% (104) |
| >1-2R | 33.3% / 41.4% (105) | 41.1% / 43.1% (175) |
| >2R | 45.3% / 43.2% (832) | 46.1% / 43.9% (738) |

The >1-2R hourly-SMA band has a lower pooled target-first rate than >2R: 38.2% versus 45.7% (-7.45 percentage points; session interval [-12.92, -2.30]). Its fair-coin-adjusted difference is -6.42 points, interval [-12.76, -0.87]. This is an exploratory negative association among many comparisons, not a validated avoid-zone or evidence that proximity causes worse forecasts.

The confluence figures illustrate why the original 4/5 result needed caution: the next wider disjoint band is 5/20 (25%), and the >1-2R band is 16/45 (35.6%). Each is too sparse under the fixed coverage rule. This is not evidence for choosing or rejecting a threshold.

## Other horizons and reward ratios

All combinations and monthly breakdowns are in summary.csv/report.json, with raw controls and outcome counts. comparisons.csv contains each nearer band versus >2R for both raw rate and excess over fair coin. The following retains all hourly-SMA combinations rather than selecting a winner.

| Window | Reward:risk | 0-0.5R | >0.5-1R | >1-2R | >2R |
|---|---|---|---|---|---|
| 5 minutes | 1:1 | 42.4% | 43.9% | 38.2% | 45.7% |
| 5 minutes | 2:1 | 15.7% | 16.2% | 14.6% | 18.0% |
| 5 minutes | 3:1 | 3.1% | 5.8% | 5.4% | 5.8% |
| Up to 60 minutes / close | 1:1 | 48.2% | 52.6% | 44.6% | 52.2% |
| Up to 60 minutes / close | 2:1 | 30.9% | 36.4% | 32.1% | 35.5% |
| Up to 60 minutes / close | 3:1 | 23.6% | 28.3% | 27.5% | 28.0% |

## Limits and next decision

Two thousand whole-session bootstrap draws preserve overlapping origins, including sessions with no members of a band. Intervals require two contributing sessions and 1,900 valid draws. All intervals are unadjusted exploratory comparisons; many families, bands, ratios and windows were inspected. Associations may reflect time of day, volatility or trend. The study does not assess fills, fees, slippage or returns.

Keep Scout unchanged. Do not widen bands again to chase a better number. If this hypothesis is pursued, the useful next evidence is additional predeclared development sessions using these unchanged categories, followed by a genuinely unexamined final evaluation after an exposure audit. July remains sealed.

## Verification and artifacts

- Five focused tests passed: band edges, missing inputs, pair-separation requirement and corrected session bootstrap.
- Independently recalculated level distances from raw saved price levels for all 2,214 contexts; <=0.5 memberships exactly match v1.
- Confirmed all inherited outcome columns are unchanged, all joins are one-to-one per origin/ratio/window, all partitions cover the full sample, and all 450 summary denominators reconcile.
- protocol.md; classifications.csv and coverage.json (saved before labels); outcomes.csv; summary.csv; comparisons.csv; report.json; verification.json; manifest.json.
- v1 source hashes verified again after completion; original outputs preserved.
