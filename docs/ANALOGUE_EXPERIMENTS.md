# Historical analogue experiments

Paper testing only. A probability is not a fill.

## Status

- Analogue is the current directional/probabilistic **research leader** among
  ghost-candle engines on the August 2026 pilot. That slice is **development**.
- Kronos-small remains a frozen benchmark. Do **not** fine-tune Kronos.
- Multi-year Nasdaq 1-minute QQQ is **already local**
  (`data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet`). Do not purchase
  Databento for this work.

## Evaluator

`python -m level_probability_lab ghost-metrics`

Adds, versus climatology estimated on **train RTH QQQ through 2023-12-29**:

- Brier, Brier Skill Score, log loss
- reliability bins (adaptive if counts are small)
- OLS calibration slope/intercept
- observation count, mean/median subsequent return per bin
- **session-block bootstrap** 95% intervals (sessions resampled, not minutes)

Contestants stay on the board: climatology, persistence, historical analogue,
Kronos-mini, Kronos-small. Losing rows are archived, never deleted.

## Leakage

Every retrieved analogue must satisfy `analogue_future_end < origin`.
`future_end` is the **bar_end** of the last horizon minute. Source timestamps
are stored. A violation raises `AnalogueLeakageError`.

## One axis at a time

Budget is recorded. Do not search hundreds of combinations.

| Axis | Values | Unlocked |
|---|---|---|
| A lookback | 15, 30, 60, 120, 240 | yes |
| B k | 10, 25, 50, 100, 200 | after A |
| C weighting | uniform, inverse-distance, gaussian | after B |
| D features | path → +volume → +vol → +tod → +prev session → +VWAP → +MA → +Bollinger → one combo | after C |

Daily features use **completed prior sessions only**.

`python -m level_probability_lab analogue-sweep --dimension lookback --max-sessions 40`

Evaluates on **2024 validation** sessions (not August). Origin stride 15
minutes. Corpus stride 5 (budget). Kronos is not re-run.

## Kronos control

One post-hoc method: inflate the median-centered q10–q90 width to 80%
coverage on earlier August days, then check later August days. Weights
unchanged. Not a protected holdout.

## Goal

Find whether any engine beats **train climatology** on later unseen sessions
with session-blocked uncertainty, not merely prettier ghost candles.
