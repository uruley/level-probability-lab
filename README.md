# Level Probability Lab

Research pipeline for estimating the probability that QQQ reaches a frozen upper
or lower price boundary first within a short horizon, using completed 1-minute
bars and SPY as market context.

**Paper testing only.** There is no brokerage connection, no live orders, and no
profit claim. A barrier being reached in historical labels does not prove that
an order would have filled or that a strategy is profitable.

Phase 1 implements data plumbing and event labels. It does **not** train a
neural network and does **not** call an LLM.

## What Phase 1 does

- Offline synthetic smoke test through normalize → validate → label
- Databento **quote-only** command (metadata; no market-data download)
- Guarded downloader (disabled, spending cap `$0` until you approve an exact request)
- NYSE regular-session calendar, UTC timestamps, no invented candles
- Labels: `upper_first` / `lower_first` / `neither`, plus quality statuses
  `ambiguous` and `incomplete` that are **never** recoded as `neither`

## Windows setup (PowerShell)

```powershell
cd C:\Users\ruley\AiStcockProbabilitydoctor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
```

Optional, only when you are ready to quote Databento:

```powershell
pip install -e ".[dev,databento]"
Copy-Item .env.example .env
# Edit .env locally. Put DATABENTO_API_KEY there.
# Never paste the key into chat.
```

## Commands

```powershell
# Offline plumbing test (no API key, no network)
python -m level_probability_lab smoke

# Unit tests
python -m pytest
python -m level_probability_lab test

# Metadata-only quote of the proposed August 2026 QQQ+SPY 1-minute pilot
python -m level_probability_lab quote --config configs/databento_pilot.yaml

# Download is blocked unless you pass every guard. Do not run this until you
# have read the quote, set a spending cap, and intend to spend credits.
python -m level_probability_lab download --config configs/databento_pilot.yaml --enable-download --i-approve-this-exact-request --spending-cap 5 --quote-manifest data\manifests\quotes\<fingerprint>.json

# Normalize/validate and build labels from a local parquet
python -m level_probability_lab validate --config configs/smoke.yaml --input data\smoke\raw_synthetic.parquet --synthetic
python -m level_probability_lab label --config configs/smoke.yaml --input data\smoke\raw_synthetic.parquet --synthetic --out-dir data\labels
```

`download` without `--enable-download`, `--i-approve-this-exact-request`, and a
positive `--spending-cap` refuses to call `timeseries.get_range`.

## Prediction task (Phase 1 labels)

| Item | Default |
|---|---|
| Target | QQQ |
| Context | SPY (as-of join at prediction time only) |
| Input | 1-minute OHLCV |
| Lookback | 120 completed regular-session minutes (30 in the smoke config) |
| Horizon | 15 elapsed minutes, same regular session |
| Boundaries | Frozen at prediction time: `close ± k * (|close| * trailing 1-minute log-return std)` |
| Calendar | NYSE (`pandas_market_calendars`), including holidays, DST, early closes |

A bar is usable only after `bar_end` plus an **assumed** publication lag
(default 0 seconds). That lag is not a historical exchange publication time.

## Pilot data proposal (not downloaded)

See `docs/DATABENTO.md` and `configs/databento_pilot.yaml`.

- Dataset: `EQUS.MINI` (derived multi-venue aggregate, **not** full SIP volume)
- Schema: `ohlcv-1m`
- Symbols: QQQ, SPY
- Dates: 2026-08-01 to 2026-09-01 exclusive
- Default authorization: off; cap `$0`

Exact cost and coverage are unknown until you run `quote`.

## Later phases (not built)

2. Validate an approved real download; historical baseline + boosted trees
3. Small causal sequence model; calibration / Brier / log loss; walk-forward
4. Extra context (IWM, vol, Treasuries, sectors) after checking each feed
5. Paper-trading simulation; optional constrained Nemotron research assistant

Nemotron is not the Phase 1 predictor.

## License / use

Local research code. Keep `.env` uncommitted. Do not log secrets.
