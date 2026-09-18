# AGENTS.md — Level Probability Lab

Read this before changing the repo. Also read `PROJECT_STATE.md` and `docs/DATABENTO.md`.

## Goal

Research-only pipeline: from completed 1-minute QQQ bars + SPY context, estimate
the probability that a frozen upper boundary is hit first, a frozen lower
boundary is hit first, or neither, within 15 elapsed minutes of the same
regular session. Phase 1 is labels and data plumbing, not a trading system.

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
