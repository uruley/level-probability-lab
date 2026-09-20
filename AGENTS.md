# AGENTS.md — Level Probability Lab

Read this before changing the repo. Also read `PROJECT_STATE.md`, `docs/KRONOS_LAB_GOALS.md`, and `docs/DATABENTO.md`.

## Goal

Active objective: Kronos Lab, a historical QQQ replay machine that supplies
completed candles to Kronos Base (Small for comparison), projects the next
five one-minute candles, reveals actual outcomes, and records baseline scores.
Integrate the acquired time-and-sales into replay and investigate measurable,
faithful explanations. See `docs/KRONOS_LAB_GOALS.md` for scope and milestones.
The older 15-minute boundary-probability pipeline is a separate research track;
do not redirect Kronos Lab work to it without a user request.
Research only, not a trading system. July 2026 is a completed final test for
trade_comparison_v1 and must not be used to retune that study.

Current priority: record where each Kronos forecast occurs relative to daily
levels, moving averages and hourly/daily Bollinger Bands; add chart overlays
and results by location before a new Scout training experiment. Future time-and-
sales features belong in a separate context/Scout branch. See the current-priority
section in `docs/KRONOS_LAB_GOALS.md` when asked about goals or next steps.
Context snapshots, selectable frozen-level overlays and exploratory grouped
counts are implemented. First matched-baseline analysis is complete; see
`data/location_evaluation_v1/RESULTS.md`. Strict confluence is too sparse for a
conclusion. Broader fixed bands are evaluated in `data/location_evaluation_v2/RESULTS.md`
without a reliable positive primary result; avoid further outcome-driven threshold
search. New Scout training remains planned; current Scout is offline and close-based.
August expansion is complete: `data/location_evaluation_v3_august/RESULTS.md`
(1134 forecasts/21 sessions). Overall five-minute 1:1 does not clearly beat
matched random direction. Hourly SMA >0.5–1R has an exploratory August signal
but lacks stable prior-month confirmation; no Scout/location rule promoted.

## Safety limits (do not violate)

- No brokerage APIs, live orders, or “this is profitable” claims.
- No Databento `timeseries.get_range` / batch job unless the user approved the
  **exact** request and a positive spending cap after a quote.
- Default: `download_enabled=false`, `spending_cap_usd=0`.
- Never ask the user to paste an API key into chat. Local `.env` only.
- Never commit `.env` or log secrets.
- Do not retry a paid request after an uncertain failure; mark `uncertain_charge`.
- Do not invent OHLCV. Do not recode `ambiguous` / `incomplete` as `neither`.
- Do not train a neural net or add an LLM-per-bar path in Phase 1.
- Do not activate Databento live/subscriptions.

## Layout

- `src/level_probability_lab/` — library + CLI
- `configs/` — YAML (`default`, `smoke`, `databento_pilot`)
- `tests/` — offline unit tests; Databento is mocked
- `data/` — gitignored artifacts

## Commands

```powershell
python -m level_probability_lab smoke
python -m pytest
python -m level_probability_lab quote --config configs/databento_pilot.yaml
```

## Label contract

Valid classes: `upper_first`, `lower_first`, `neither`.

Quality statuses (not classes): `ambiguous` (same bar touches both bounds;
order unknown), `incomplete` (horizon past session close, coverage gap, missing
elapsed minutes, insufficient lookback, degenerate vol).

Horizon is elapsed time on a minute grid, not “the next 15 rows.”

## Next phases

Documented in README / PROJECT_STATE. Do not implement 2–5 unless asked.
