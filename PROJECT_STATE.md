# PROJECT_STATE.md

## Goal

Level Probability Lab: eventually train a numerical model on ~8 years of
intraday OHLCV (coverage and price permitting) to estimate P(upper first),
P(lower first), P(neither) for QQQ using completed bars, volume, and SPY
context. Research / paper testing only.

## Decisions (Phase 1)

- Project root: `C:\Users\ruley\AiStcockProbabilitydoctor` (was empty).
- Package: `level_probability_lab`, CPU-only Python 3.10+, Windows/PowerShell.
- Calendar: NYSE via `pandas_market_calendars`.
- Timestamps stored in UTC. Databento `ts_event` = bar start. Usable time =
  bar_end + assumed publication lag (default 0s).
- Pilot feed: `XNAS.ITCH` `ohlcv-1m` QQQ+NVDA+TSLA, 2026-08-01..2026-09-01.
  Nasdaq TotalView, venue-specific volume (Nasdaq prints only). EQUS.MINI and
  CME futures were quoted then dropped for this first real pull. Prediction
  target remains QQQ; NVDA and TSLA are context.
- Vol scale: sample std of 1-minute log returns on completed lookback bars.
- Boundaries frozen at prediction time: `ref ± k * vol_scale`.
- Nemotron / LLMs: out of scope for Phase 1.
- Databento download: guarded; two approved pulls completed (August pilot and 2018–2026 history).

## Implemented

- Config, local parquet storage, manifests
- Synthetic generator + smoke pipeline
- Normalize / session grid / no_trade vs coverage_gap
- Validation (sort, duplicates, OHLC, volume, UTC)
- Event labels + context as-of join
- Quote-only Databento adapter + guarded download
- pytest suite (30 tests, all passing on 2026-09-17)
- README, AGENTS.md, docs/DATABENTO.md
- Live quote and one approved download have been run:
  `XNAS.ITCH` `ohlcv-1m` QQQ+NVDA+TSLA, 2026-08-01..2026-09-01,
  fingerprint `9e345ac447080e79c55152fa9f7c14ae830acc8426685d437fa251cfb07e2323`,
  quoted cost $0.0355, spending cap $1, state completed.
  Raw: `data/raw/XNAS_ITCH_9e345ac44708.ohlcv-1m.dbn.zst` and `.parquet`.
  Labels: `data/labels/pilot_aug2026/`. A month is a pipeline check, not an edge.
- Multi-year download completed 2026-09-17:
  fingerprint `a0bdd1f87cd32d5ef6c64228866e3be8db21850562b2288ecb45b9b79ada6fa6`,
  `XNAS.ITCH` `ohlcv-1m` NVDA+QQQ+TSLA, 2018-05-01T00:00:00Z..2026-09-01T00:00:00Z,
  fresh get_cost $3.1572, cap $5, 5,044,735 rows.
  Raw: `data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.dbn.zst` and `.parquet`.
  Databento warned of degraded days 2021-07-07, 2021-10-26, 2022-09-19.

## Unresolved / limits

- History file is local; full-history normalize/label and models are not run yet.
- Metadata billing residual uncertainty remains.
- Adapter cannot see or cap Databento’s actual invoice.
- Publication lag is assumed 0s, not measured.
- Prices unadjusted (NVDA/TSLA splits in history).
- No model has been fit. August is development, not holdout.
- Ghost-candle replay (2026-08-14 QQQ): Kronos-small on RTX 5070 via project
  `.venv` cu128, 266 forecasts of 5 minutes / 50 paths. Artifacts in
  `data/ghost_candles/2026-08-14/`. Isolated under
  `src/level_probability_lab/ghost_candles/`. Not a trading signal.
- Direction metric corrected: persistence/zero-change is neutral, not a
  failed direction call. See `docs/GHOST_CANDLE_METRICS.md`. Pooled eval
  across complete local QQQ sessions is `ghost-eval` (append-only ledger
  under `data/ghost_candles/experiments/`).

## Next steps

History file validated: `docs/HISTORY_VALIDATION.md`,
`data/reports/history_validation.json`. Usable for the frozen experiment
with documented halt-day minute gaps, 6 after-hours NaN rows to drop, and
unadjusted TSLA/NVDA splits. Next: label at k in {2,3,4}, then baselines
and trees. Do not score August 2026 as holdout.

See `docs/LABEL_AUDIT.md` and `docs/EXPERIMENT_SPEC.md`.

## Phase map (do not build all at once)

- Phase 2: real-data validation, deliberate history expansion, baseline + trees
- Phase 3: small causal sequence model, walk-forward, holdout, Brier/log loss
- Phase 4: extra context feeds after field-level checks
- Phase 5: paper-trading sim; optional constrained Nemotron assistant; no live trading
