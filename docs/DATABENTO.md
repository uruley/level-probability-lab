# Databento adapter notes (Phase 1)

This file records the official sources used to implement the quote/download adapter.
Do not treat it as a live price list. Costs and schema-level coverage must be
read from `metadata.get_cost` / `get_dataset_range` at quote time.

## Methods used

Historical Python client (`databento.Historical`), documented at
https://databento.com/docs/api-reference-historical

Quote-only (no market-data stream):

- `metadata.get_dataset_range(dataset)`
- `metadata.list_schemas(dataset)`
- `metadata.get_dataset_condition(dataset, start_date, end_date)`
- `metadata.list_unit_prices(dataset)`
- `metadata.get_record_count(...)`
- `metadata.get_billable_size(...)`
- `metadata.get_cost(...)`

Billable market data (guarded download only):

- `timeseries.get_range(...)` — client warning: calling this incurs a cost

Not used in Phase 1:

- `databento.Live`
- `batch.submit_job` / batch download
- subscriptions

`get_cost` / `get_record_count` may over-report when the time range is not a
discrete multiple of 10 minutes
(https://databento.com/docs/api-reference-historical).

## Billing (what we can and cannot enforce)

Source: https://databento.com/docs/faqs/usage-pricing-and-data-credits

- Historical data is billed per uncompressed binary byte of market data sent.
- Streaming: if the connection drops, remaining unsent data is not charged.
  Bytes already sent may be charged. This tool cannot see the invoice.
- Batch jobs (not used here) are billed once; re-download within 30 days is free.
- After any exception that occurs once `get_range` has been invoked, the local
  manifest is `uncertain_charge` and retries are refused until
  `--acknowledge-prior-failure`.
- Metadata exists to estimate cost before a timeseries request. Databento does
  not publish a single sentence that metadata HTTP calls are never billed.
  Residual uncertainty is printed on every quote.

New-account credits ($125) are not authorization to spend them.

## OHLCV conventions

https://databento.com/docs/schemas-and-data-formats/ohlcv

- Schema id `ohlcv-1m`.
- `ts_event` is the inclusive start of the bar.
- If no trade occurs in the interval, no record is printed.

Missing minutes are therefore **not** automatically coverage holes. Isolated
missing regular-session minutes are flagged `no_trade`. Long contiguous holes
are `coverage_gap`. OHLC is never invented
(https://databento.com/docs/examples/basics-historical/ohlcv-resampling).

## Pilot dataset choice (not auto-downloaded)

Proposed quote (see `configs/databento_pilot.yaml`):

| Field | Value |
|---|---|
| dataset | `EQUS.MINI` |
| schema | `ohlcv-1m` |
| symbols | QQQ, SPY |
| start | 2026-08-01 |
| end | 2026-09-01 (exclusive) |

### EQUS.MINI — proposed

- Docs: https://databento.com/docs/venues-and-datasets/equs-mini
- History start (blog): 2023-03-28
  https://databento.com/blog/databento-us-equities-mini-now-available
- Derived multi-venue aggregate (ATS + selected Reg NMS). Venue ids are
  anonymized (`publisher_id` is `EQUS.MINI.EQUS`).
- OHLCV prices **and volume are aggregated across component venues**.
- This is **not** full SIP/NMS consolidated volume.
- Does not by itself provide ~8 years of history.

Chosen for the pilot because it covers both QQQ and SPY at 1-minute with
multi-venue aggregated volume. Not chosen because it is cheapest.

### XNAS.ITCH — not the pilot

- https://databento.com/datasets/XNAS.ITCH
- Nasdaq TotalView, venue-specific, available from 2018-05-01.
- Volume is Nasdaq-only. SPY is listed on NYSE Arca; Nasdaq prints are a
  partial market. Rejected as the joint QQQ+SPY pilot feed for that reason,
  not because of price.

### EQUS.SUMMARY — not usable here

- https://databento.com/docs/venues-and-datasets/equs-summary
- Consolidated daily volume / `ohlcv-1d` / statistics / definition only.

## Limits

This adapter cannot activate live data, cannot guarantee provider-side charges,
and will not download unless download is enabled, the exact request is approved,
a positive spending cap is set, and a fresh `get_cost` is at or under that cap.
