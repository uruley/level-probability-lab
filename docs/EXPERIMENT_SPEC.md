# Frozen experiment specification (v1)

**Subsequent study note (2026-09-19):** this is the historical fifteen-minute
barrier-study specification. The user has since authorized a separate
[five-minute Kronos/trade study](THREE_MONTH_STUDY_PROTOCOL.md). May and June
2026 are now development/validation data for that work and must not be called
untouched holdout in future reports. July is evaluated only after that new
study's settings are frozen. The multi-year candle download referenced below
was completed on 2026-09-17; its older acquisition status is retained as history.

Status: **specified, not run**. No model has been fit. The multi-year file
has **not** been purchased. This document freezes dates, labels, and
comparisons before model selection.

Related: `docs/LABEL_AUDIT.md`, `configs/experiment_v1.yaml`,
`configs/history_xnas_ohlcv1m.yaml`.

## Identity

- Task: estimate P(upper first), P(lower first), P(neither) for **QQQ**
  over a 15-minute same-session horizon.
- Feed: `XNAS.ITCH` 1-minute OHLCV. **Nasdaq-feed research.** Prices,
  volume, and labels are venue-specific. Not consolidated U.S. tape. Not
  a fill or a trading edge.
- Context: last completed NVDA and TSLA Nasdaq bars with `usable_at <= prediction_time`.
- Out of scope for this spec: options, full-month trade prints, Nemotron,
  sequence models, live orders.

## Proposed purchase (not authorized)

Exact request (Databento `end` exclusive):

| Field | Value |
|---|---|
| dataset | `XNAS.ITCH` |
| schema | `ohlcv-1m` (listed for this dataset; schema range 2018-05-01T00:00:00Z to 2026-09-17T04:00:00Z) |
| symbols | NVDA, QQQ, TSLA (`raw_symbol`) |
| start UTC inclusive | `2018-05-01T00:00:00Z` |
| end UTC exclusive | `2026-09-01T00:00:00Z` |
| fingerprint | `a0bdd1f87cd32d5ef6c64228866e3be8db21850562b2288ecb45b9b79ada6fa6` |
| estimated cost | **$3.1572** |
| records / bytes | 5,044,735 / 282,505,160 |
| proposed ceiling | **$5.00** (not authorization) |

Per-symbol quotes (same window): NVDA $1.002, QQQ $1.046, TSLA $1.108.
Each symbol has records in the dataset-open week (2018-05-01..05-08) and in
the last week before end (2026-08-24..09-01). Symbology resolve: status OK,
`not_found` empty, mappings from 2018-05-01 through 2026-09-01.

Dataset condition on this range: 2173 `available` days, 3 `degraded`
(2021-07-07, 2021-10-26, 2022-09-19). Treat those sessions as
`incomplete` if bars are missing or flagged; do not impute.

Manifests:

- `data/manifests/quotes/a0bdd1f87cd32d5ef6c64228866e3be8db21850562b2288ecb45b9b79ada6fa6.json`
- `data/manifests/quotes/history_coverage_a0bdd1f87cd32d5ef6c64228866e3be8db21850562b2288ecb45b9b79ada6fa6.json`

Download remains disabled until an explicit approval of **this fingerprint**
and a spending cap ≥ the fresh `get_cost`.

## Chronological partitions (session dates, NYSE)

August 2026 was inspected and is **development**, not holdout.

| Role | First session | Last session | NYSE sessions |
|---|---|---|---:|
| Train | 2018-05-01 | 2023-12-29 | 1427 |
| Validation / calibration | 2024-01-02 | 2024-12-31 | 252 |
| Protected holdout | 2025-01-02 | 2026-07-31 | 395 |
| Development (already inspected) | 2026-08-03 | 2026-08-31 | 21 |

Overlap rule: drop any training (or val) example whose `horizon_end` is
strictly after the next partition’s first regular-session open. With
same-session 15-minute labels and session-date cuts, that should drop
nothing at the year boundaries; still enforce it in code.

Do not use development (August 2026) for reported Brier/log loss or for
model selection. Use it only for label audit, barrier-grid inspection, and
pipeline checks.

Protected holdout: one look at the end, after train/val choices are frozen.
No retuning after holdout scores.

## Labels

- Builder: `src/level_probability_lab/labeling.py` (see label audit).
- Frozen comparison distances: **k ∈ {2.0, 3.0, 4.0}** with
  `upper = close + k * |close| * std(1-min log returns, 120-minute lookback)`.
- Report each model at each k separately. Do not rank models across k.
- Valid classes: `upper_first`, `lower_first`, `neither`.
- Keep `ambiguous` and `incomplete` visible. Score probabilities on valid
  classes. Publish sensitivity that assigns all ambiguous rows to each class
  in turn (including neither) without making that the primary number.

## Preprocessing

Fit only on **train**:

- Any feature scaler, volume transform, or split-adjustment rule.
- Tree hyperparameters, if any, selected on validation only.

Row-local quantities (lookback vol, frozen bounds) use only completed bars
at or before prediction time. No future interpolation of NVDA/TSLA.

Corporate actions: unadjusted Nasdaq prices. Flag split sessions. Do not
feed raw NVDA/TSLA price levels across TSLA 2020-08-31, TSLA 2022-08-25, or
NVDA 2024-06-10. NVDA’s split sits inside **validation**; context features
must be split-safe before that year is scored.

## Models (same dates, same labels)

All four produce a 3-vector that sums to 1.

1. **Constant historical class probabilities** from train valid-class
   frequencies (one vector, repeated).
2. **Conditional historical frequencies** on train: bins of time-of-day,
   lookback volatility, and current distance-to-bound / vol (or k-normalized
   range). Laplace or train-only smoothing. No test information in bins.
3. **Boosted tree, QQQ only** (completed-bar QQQ returns, range, Nasdaq
   volume, time-of-day, lookback vol).
4. **Same tree plus NVDA/TSLA as-of context** (returns/volume, not raw
   post-split price levels).

No sequence model in this spec.

## Metrics (out of sample)

On validation, then once on holdout, for each k and each model:

- Brier score (multiclass)
- Log loss
- Classwise reliability (plots + tables)
- Counts: valid N, ambiguous N, incomplete N, and reasons
- Improvement vs model 1 (constant) and vs model 2 (conditional histogram)
  on the **same** rows

Calibration without a baseline comparison is not an edge. None of these
metrics is a trading P&amp;L.

## Validation checklist after download (before trees)

- Missing NYSE sessions vs calendar; the three degraded dates above
- Duplicate timestamps; UTC; bar_start &lt; bar_end
- OHLC consistency; nonnegative volume
- Cross-symbol as-of: context `usable_at <= prediction_time`
- Split-day flags for TSLA/NVDA
- Label overlap into val/holdout = 0

## Local artifacts to keep

- Configs: `configs/history_xnas_ohlcv1m.yaml`, `configs/experiment_v1.yaml`
- Quotes and coverage JSON under `data/manifests/quotes/`
- August audit JSON under `data/reports/`
- After approval: raw DBN, parquet, labels, experiment log
