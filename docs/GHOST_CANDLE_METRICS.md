# Ghost-candle evaluation metrics

Paper testing only. No trading claim.

## Origin

`origin_close` is the close of the last **completed** input bar. Every
horizon is scored against that price. Subsequent actuals are unknown at
forecast time.

## Point error

`median_close_abs_error` = |median(sample closes at horizon h) − actual close|.

The displayed ghost candle is a **real sampled path** (nearest to the
median close vector). Distribution metrics never average OHLC components
independently.

Persistence is a flat close at `origin_close` with high/low = origin ±
median lookback range / 2. It is a point baseline, not a directional model.

## Direction (corrected)

`move_sign(value, origin)` is +1 / −1 / 0 (deadzone default 0).

Forecast **stance** = `move_sign(median_close, origin_close)`.

Persistence has stance 0 at every horizon.

`directional_hit` is **undefined (NaN)** when stance is 0. Persistence
therefore does **not** receive a ~0% directional accuracy. That was the
bug in the first replay: zero-change was treated as a wrong direction
call whenever price actually moved.

On the non-neutral subset, hit = 1 iff stance equals
`move_sign(actual_close, origin_close)`.

Report separately: `neutral_rate`, `n_directional`, `directional_accuracy`.
Do not publish “directional accuracy including neutrals as misses.”

## Sample distribution (Kronos and analogues)

For each horizon, over all kept sample paths:

- median close and close quantiles q10/q25/q50/q75/q90
- P(close > origin), P(close < origin)
- high and low quantiles
- range (high−low) distribution
- max upside excursion to h: median over paths of max(high_1..h − origin)
- max downside excursion to h: median over paths of min(low_1..h − origin)

Persistence has no probability distribution; `p_close_gt_origin` and
Brier are NaN for that engine.

## Calibration

Event y = 1{actual_close > origin}. Model p = sample fraction with
close > origin. Brier = (p − y)². Reliability tables bin p into 10
equal-width bins and compare mean p to empirical frequency.

## Historical analogues

Lookback path is percent-of-last-close, plus lookback return vol, high-low
range / last close, and relative volume. Distance is Euclidean on the path
plus 0.25 × sum of log-ratio scalar distances. Weights are fixed, not fit
on 2026-08-14.

Eligible windows: lookback end **and** the subsequent 5-minute horizon
must finish strictly before the origin timestamp (no future leakage).
Overlapping retrieved windows are allowed and disclosed
(`n_overlapping_pairs`, mean/max overlap fraction, distinct sessions).

## Slices

2026-08-14 is **debug**, not a holdout. Claims use all complete local
pilot sessions, with a secondary slice that drops the debug day.

Breakdowns: horizon +1…+5, opening hour (09:30–10:30 NY), midday,
final two hours (14:00–16:00 NY), lookback-vol above/below pooled median,
lookback trend vs range (|net|/high-low ≥ 0.5).
