# Kronos + time-and-sales: prospective protocol

Frozen before reviewing baseline scores or July outcomes on 2026-09-19.
Research question: does Nasdaq trade-level information improve five-minute
QQQ close forecasts beyond the same model with candle-only information?

## Authorization and scope

The user requested agents to run the baseline, acquire a quoted matching trade
sample, and test incremental information. They explicitly approved the exact
`XNAS.ITCH` / `trades` / `QQQ` / `raw_symbol` request from
2026-05-01T00:00:00Z inclusive through 2026-08-01T00:00:00Z exclusive,
after its $2.484871119261 quote, with a $3 cap. It completed once. This
authorizes no other data request, subscription, or brokerage operation.

This is a separate five-minute study, not the old fifteen-minute boundary
classification experiment. May and June 2026 are deliberately consumed for
development and validation and must not later be called untouched holdout in
the older experiment. August 2026 was already inspected. July is reserved
from evaluation in this new study until the fitting and selection artifacts
are frozen. That does not prove absence from any prior upstream training or
historical analogue corpus; no universal pristine-holdout claim is made.

## Calendar split and fixed baseline

| Role | NY regular sessions | Permitted use |
|---|---|---|
| Development | May 2026 | Data quality, scaling, ridge fitting |
| Validation | June 2026 | Choose from the fixed regularization grid |
| Final test | July 2026 | One evaluation after the selection artifact is frozen |

QQQ one-minute bars come from the existing local XNAS.ITCH parquet, with no
new candle purchase. The baseline contains 41 May/June sessions, 54 origins
per session, 2,214 common origins for each engine. For each origin:

- 120 contiguous completed regular-session candles.
- Origin at session open + 119 minutes, then every 5 elapsed minutes.
- Five subsequent elapsed-minute bars within the same session.
- Base and Small pinned revisions, 25 paths, seed 42, temperature 1, top_p 0.9.
- Approximate amount input = volume × close, frozen to the existing adapter.
- A constant origin-close prediction is the point baseline.

All models use identical eligible origins. Missing/invalid input or outcomes
are excluded with a count; never fabricated or treated as a successful forecast.
Forecast records are saved before actual outcomes are scored. Files and source
code are fingerprinted. Forecasts are resumable without overwriting completed
records. The full May/June runner cannot read July outcomes.

Baseline metrics: MAE and RMSE in dollars per horizon, empirical-up Brier
against May climatology, pointwise sampled close interval coverage and width,
and direction conditional on both actual and predicted moves being nonzero.
This conditional direction denominator differs from counting actual zero
moves as misses; do not compare those numbers without aligning definitions.
Persistence has no direction call or probabilistic interval. May climatology
scores in May are descriptive; June is the forward comparison.

## Trade data quality and causal timing

Download includes all available hours. Modeling uses regular-session data.
Receive timestamps determine minute buckets and availability, matching
Databento OHLCV construction. Event timestamps remain provenance; do not use
an event-time bar join that admits trades not received by the forecast time.
Preserve record order for timestamp ties, price conversion exactly once,
unknown trade-side volume, and quality flags. Sequence gaps alone are not
evidence of missing prints in a trades-only stream.

Reaggregate May/June OHLCV and compare with the original minute bars before
fitting. Audit invalid timestamps, prices, sizes, side codes and bad flags.
Reject affected feature windows and apply identical retained origins to raw
Kronos, candle-only correction, trade correction and persistence. Report
reconciliation coverage and all exclusions. If matching cannot be established,
stop the incremental comparison rather than attributing data differences to
predictive lift. July has an identical quality policy; no policy retuning there.

## Fixed paired experiment

Primary model: **Kronos Base**, selected before reading any baseline results.
Small remains a separate raw benchmark. No Kronos weights are fitted.

Fit two ridge corrections of the Base median-close forecast, independently at
horizons 1–5. Response is actual-minus-Base predicted close, divided by origin
close and multiplied by 10,000 (basis points). Add the predicted correction
back to the unchanged Base forecast.

The control uses only candle-derived features and Base outputs:

- Log returns 1, 5, 15, 60 minutes; full 120-minute return is last close / first open
  because 120 candles contain 119 close-to-close returns.
- Standard deviation of one-minute log returns over 15 and 60 minutes.
- Mean high-low range divided by origin close over 15 and 60 minutes.
- log1p of last volume, and last volume / trailing 15-minute mean volume.
- Sine and cosine of time within the regular session.
- All five Base median forecast returns in basis points.

The trade arm adds trailing 1/5/15-minute means of completed-minute trade count,
mean size, maximum-trade share of volume, size coefficient of variation,
VWAP-minus-close distance in basis points, within-minute log-price realized
variance, known-side signed fraction of total volume, and unknown-side volume
fraction. No spread, book-depth, or inferred unknown-side aggressor feature.

Standardization and coefficients are fitted on May only. Both arms use the
same fixed ridge grid `{1,10,100}`. Each arm selects one regularization value
by June horizon 5 MAE and uses that value for all horizons. Do not refit on June.
Save coefficients, scalers, feature order, chosen penalties, data/code hashes,
and the June selection table before any July fit or evaluation. June results
after this selection are validation results, not final test evidence.

## One final test and decision rule

Only after the frozen selection artifact exists and passes review, evaluate
the fixed models on July once. Raw Base and Small, persistence, candle-control
correction and trade correction share the same eligible test origins.

Primary endpoint: July horizon 5 MAE of trade correction minus candle-only
correction. Lower is better. Report its paired session-block bootstrap 95%
interval, 2000 replicates, seed 20260919. Evidence threshold is both:

1. At least 1% relative MAE reduction versus candle-only correction.
2. The upper endpoint of the paired difference interval is below zero.

Report every horizon, both months' validation/development outcomes, RMSE,
exclusion counts, and raw baselines regardless of the primary result. Do not
pick the best horizon, discard losing engines, or retune after July. Failure
to clear the threshold means this study did not establish incremental value;
it does not prove trade data can never help. Intraday observations share
information; whole sessions, not rows, are bootstrap units. Cross-session
dependence and this short market period still limit inference.

No trading-profit claim follows from forecast errors. LLM explanation quality
is not part of this numerical test.
