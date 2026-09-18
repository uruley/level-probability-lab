# Label audit (August 2026 development sample)

**This sample is development data, not a holdout.** It was inspected before
the multi-year download. Do not report August scores as untouched test
performance.

Feed: **Nasdaq TotalView (`XNAS.ITCH`)**. OHLC, volume, and therefore barrier
labels are **Nasdaq-venue prints**, not SIP/consolidated tape. A bound being
touched does not prove an order would have filled.

Source files:

- `data/labels/pilot_aug2026/normalized.parquet`
- `data/labels/pilot_aug2026/labels.parquet`
- Machine-readable copy: `data/reports/label_audit_august2026.json`

## Formula (implemented)

Prediction target: **QQQ** only. NVDA and TSLA are as-of context, not labels.

1. A 1-minute bar has `bar_start` = Databento `ts_event` (inclusive start).
2. `bar_end` = `bar_start + 1 minute`. The bar is an input only after it is
   complete.
3. `usable_at` = `bar_end + publication_lag`. Lag is **assumed 0 seconds**.
   This is not a historical exchange publication timestamp.
4. Lookback is **the same regular session only**. Observed QQQ closes with
   `bar_start` in `[prediction_bar_start − 119 minutes, prediction_bar_start]`.
   That is up to **120 completed 1-minute bars**, including the prediction bar
   when every minute exists.
5. Require at least **60** observed lookback closes (`min_observed_for_vol`).
   Otherwise status = `incomplete` / `insufficient_lookback`.
6. `vol_log` = sample standard deviation (**ddof = 1**) of 1-minute log
   returns `log(close_t / close_{t-1})` on those lookback closes.
   Units: dimensionless (per minute).
7. `vol_scale` (dollars) = `|reference_close| * vol_log`.
   `reference_close` is the prediction bar’s close.
8. Frozen bounds, never updated inside the horizon:

   - `upper = reference_close + k_up * vol_scale`
   - `lower = reference_close - k_down * vol_scale`

   Implemented Phase 1 config: `k_up = k_down = 1.0`.
9. Horizon is **15 elapsed minutes after `bar_end`**, on a 1-minute grid:
   bar starts in `[bar_end, bar_end + 15 minutes)`. This is not “the next 15
   rows.” The window must finish before that session’s regular close or the
   row is `incomplete` / `horizon_beyond_session`.
10. Walk those minutes in time order. `no_trade` minutes do not touch a bound.
    If one bar’s **high ≥ upper and low ≤ lower**, label = `ambiguous`
    (tick order unknown). Never infer path from OHLC. Never recode
    `ambiguous` or `incomplete` as `neither`.

`k` is a multiple of the **1-minute** log-return sigma, not of a 15-minute
sigma. If 1-minute returns were iid, a 15-minute 1-sigma move is about
`sqrt(15) ≈ 3.87` one-minute sigmas. So `k = 1` is a tight band relative to
the 15-minute horizon.

Verified on August labels:

- Every row has `horizon_end - horizon_start = 15 minutes`.
- `prediction_time == prediction_bar_end` (lag 0).
- `lookback_last_start <= prediction_bar_start` (no future bars in vol).

## August 2026 counts (k = 1, as implemented)

Denominator **A** = all QQQ regular-session prediction times = **8190**
(21 sessions × 390 minutes).

Denominator **V** = valid classes only = **6583**.

| Status | Count | /8190 (all) | /6583 (valid only) |
|---|---:|---:|---:|
| `upper_first` | 3239 | 39.55% | 49.20% |
| `lower_first` | 3336 | 40.73% | 50.68% |
| `neither` | 8 | 0.10% | 0.12% |
| `ambiguous` | 53 | 0.65% | — |
| `incomplete` | 1554 | 18.97% | — |

Incomplete reasons (still /8190):

| Reason | Count | Note |
|---|---:|---|
| `insufficient_lookback` | 1239 | 21 × 59 first minutes (`min_observed_for_vol` = 60) |
| `horizon_beyond_session` | 315 | 21 × 15 last minutes |

Quality statuses are **not** dropped from the published table. Primary
probability scores (Brier, log loss) use **valid classes only**, with
ambiguous/incomplete counts always shown.

At `k = 1`, median frozen half-width on rows with bounds:

- **$0.21** (p10 $0.13, p90 $0.42)
- **0.030%** of QQQ (p10 0.018%, p90 0.059%)

That is why `neither` is almost empty. This is a definition issue, not a
trading result.

## Development barrier grid (August only)

Same labeler, same data, only `k` changes. Distances are medians of
`k * vol_scale` in dollars and percent of QQQ. **Do not pick `k` to force
balanced classes.** Incomplete counts stay 1554 for every `k`.

| k | half-width p50 | % of QQQ p50 | upper | lower | neither | ambiguous | valid N |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $0.21 | 0.030% | 3239 | 3336 | 8 | 53 | 6583 |
| 2 | $0.42 | 0.059% | 2796 | 2799 | 1035 | 6 | 6630 |
| 3 | $0.64 | 0.089% | 1884 | 1831 | 2912 | 9 | 6627 |
| 4 | $0.85 | 0.118% | 1188 | 1146 | 4296 | 6 | 6630 |
| 5 | $1.06 | 0.148% | 688 | 675 | 5273 | 0 | 6636 |

Frozen comparison set for later models: **k ∈ {2, 3, 4}**. Compare models
**within one k**. Higher accuracy at a different k is not a better model.

`k = 1` remains the implemented default and is too tight for a three-way
probability task. `k = 5` is kept out of the comparison set because
`neither` dominates; that is a statement about the definition, not a claim
that balanced `k = 3` is “best.”

## Ambiguous sensitivity (k = 1)

53 same-bar both-bound rows (0.65% of 8190). Primary protocol: leave them
out of Brier/log loss, keep them in the quality table.

Sensitivity only (not the main score): assigning all 53 to one class would
move that class’s count by 53. Silently calling them `neither` is forbidden.

## Data integrity (August)

- Symbols present: QQQ, NVDA, TSLA.
- 21 NYSE sessions, no early close in this month.
- Regular-session minutes: 8190 per symbol. **0** coverage-gap rows, **0**
  no-trade rows in the normalized RTH grid (these names printed every minute).
- 0 duplicate `(symbol, bar_start)`.
- 0 stale NVDA or TSLA as-of joins at prediction time.
- Discontinuity flags: 0 overnight jumps above the 8% log-return threshold
  in this month (no split in August 2026).

Known later-history corporate actions (not in this August file; will matter
after the multi-year pull; Databento prices are **unadjusted**):

- TSLA 5-for-1, 2020-08-31
- TSLA 3-for-1, 2022-08-25
- NVDA 10-for-1, 2024-06-10

Same-session 15-minute QQQ labels do not cross those overnight prints. Do
**not** use raw NVDA/TSLA price *levels* as features across a split. Prefer
returns, or split-adjust context on training-only rules.
