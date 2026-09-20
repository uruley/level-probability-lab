# QQQ time-and-sales comparison: frozen plan

Prepared 2026-09-19. Research only. The exact three-month request was approved
after the quote with a $3 cap and downloaded once successfully. The fresh
estimate was $2.484871119261; the provider invoice is not visible here. July
price outcomes have not been inspected in preparing this plan.

## Exact quote and approval boundary

Both requests use dataset `XNAS.ITCH`, schema `trades`, symbols `[QQQ]`, and
`stype_in=raw_symbol`. Starts are inclusive; ends are exclusive.

| Request | Start UTC | End UTC | Quote USD | Records | Billable bytes |
|---|---|---|---:|---:|---:|
| Three months, all available hours | 2026-05-01T00:00:00Z | 2026-08-01T00:00:00Z | 2.484871119261 | 9,264,271 | 444,685,008 |
| Optional one-session setup | 2026-05-04T13:30:00Z | 2026-05-04T20:00:00Z | 0.026237905025 | 97,822 | 4,695,456 |

The three-month request includes extended hours; only regular-session completed
minutes will enter modeling. Metadata reports `trades` available from
2018-05-01 through 2026-09-19 and 66 dataset-condition entries, all `available`,
for the study interval. This does not replace symbol/session coverage checks.
Billable bytes describe uncompressed data, not compressed disk footprint.

Full request fingerprint:
`81b52cd2b2a9ffe4fabc51f79efe308f93884f4aecadc08f5a727d413de89239`.
Sample fingerprint:
`c4dc888c7c82b506471cf3ae69714e9cd8090cf40d9f208e4bebb99acb52ae03`.
Quotes were obtained at 15:12:54 and 15:12:59 UTC on 2026-09-19.

Manifests: `data/manifests/quotes/<fingerprint>.json`; combined summary:
`data/manifests/quotes/trades_study.json`. Reproduce metadata only with
`.venv/Scripts/python.exe scripts/quote_trades_study.py`.

Recommend requesting approval for the full exact request with a **$3 cap**.
The optional sample overlaps the full request; choose one acquisition path to
avoid paying twice for those records. A sample-only alternative cap is $0.05.
Neither suggested cap is authorization: the config retains
`download_enabled: false` and `spending_cap_usd: 0.0`. A fresh cost must fit
the approved cap before any paid call. The adapter now preserves the requested
schema in output filenames, and the CLI bypasses the OHLCV decoder for trades. Any uncertain
paid failure must stop without automatic retries.

## Field contract and limitations

Trades carry price, size, event and receive timestamps, side, sequence, flags,
publisher and instrument identifiers. `B` indicates a buy aggressor, `A` a
sell aggressor, and `N` unknown. Price integers use a 1e-9 scale; use the
library's documented conversion once, never twice. [Trades schema](https://databento.com/docs/schemas-and-data-formats/trades)

XNAS.ITCH is Nasdaq venue data, not the consolidated US tape. Non-displayed
Non-Cross and Cross messages have unknown side. Executions with price omit
the synthetic trade when non-printable. Preserve unknown-side volume rather
than calling it balanced or assigning a buy/sell direction. Here
`ts_in_delta = ts_recv - ts_event`; it is not extra information. [Dataset supplement](https://databento.com/docs/venues-and-datasets/xnas-itch)

Use `ts_recv` for information availability and minute aggregation. Databento's
OHLCV interval is based on trade receive time, with `ts_event` labeling the
inclusive interval start. No trades means no printed bar. A minute's trade
features become eligible at its end, never at its start. Check reaggregated
OHLCV against existing bars before fitting anything. [OHLCV schema](https://databento.com/docs/schemas-and-data-formats/ohlcv)

Preserve file order as a deterministic tie-break for equal receive timestamps.
Sequence is venue metadata, not a globally unique trade ID; do not drop
records on sequence alone or treat gaps in a trades-only stream as lost data.
Retain quality flags and test bits with bitwise AND. Bad receive timestamps
and possible book gaps need an exclusion/audit policy fixed using May data.
Never silently repair timestamps from future observations. [Standards](https://databento.com/docs/standards-and-conventions/common-fields-enums-types)

## Experiment, not an explanation test

Freeze May for development, June for validation, and July as sealed test.
Check the prior experiment ledger for July exposure before claiming it is an
untouched holdout. Reading metadata counts is not inspecting price outcomes.
Use session calendar boundaries, not fixed UTC assumptions on arbitrary dates.
Reject origins lacking complete historical lookback or five elapsed future
minutes. Record every rejection and apply identical eligibility to all arms.

Keep Kronos inputs and weights unchanged. Raw trades cannot be appended to
its current candle input contract. Candidate causal features over completed
1/5/15-minute windows: trade count/rate, mean size, size dispersion, VWAP-close
distance, within-minute realized price variation, interarrival statistics,
known-side signed volume fraction, unknown-side volume fraction, and signed
imbalance among known-side trades. Keep unknown-side features separate.
Large-trade thresholds, standardization, clipping and imputation must be fit
on development data only. No quote spread or book depth claims from trades.

Use three paired arms at exactly the same origins: frozen Kronos; a ridge
residual correction using candle-only features; the same ridge correction
with trade features added. Fit each horizon's actual-minus-Kronos close
residual on May. Candle controls include past returns, ranges, volume,
time-of-session, and Kronos forecast outputs. Select regularization from a
small recorded grid on June, identically for both correction arms. Freeze
everything before one July pass. No neural training or LLM-per-bar loop.

Primary comparison is the incremental change from candle-control correction
to trade-augmented correction, not merely improvement over raw Kronos. Score
close MAE by horizon and session, with the unchanged-price baseline retained.
Report RMSE as secondary, direction with explicit neutral handling, and
paired session-level differences with a fixed-seed block bootstrap. Overlapping
origins are correlated: do not count them as independent trials. Choose the
primary horizon/aggregate and practical improvement threshold before unsealing
July; report all horizons regardless of which looks best.

The setup acceptance gate is reconciled OHLCV, audited side/quality coverage,
causal cutoffs passing offline tests, and matched-origin reports. The final
claim is limited to this venue and period. Three months can establish a
workable experiment; it cannot establish all-regime performance or profits.
