# Saved recording review

The bottom **Recording & five-minute results** panel reads saved Webull candles
and immutable five-minute forecasts. Choose QQQ, TSLA or NVDA and a recorded
date. It refreshes every 15 seconds and never starts a feed, runs inference,
or calls Jev. Recording still depends on the existing live browser loop.
Freshness is inferred from saved candle time; it is not proof a worker is running.

Daily summaries separate model revision, lookback and path count. +5 close MAE
and unchanged-price MAE use identical complete forecasts. High/low MAE uses
valid sampled OHLC paths across five candles; unavailable ranges remain missing.
Target/stop uses existing 1:1/2:1/3:1 candle-order rules. Early touches can resolve
before five minutes, whereas full-window close/range metrics wait. Gaps remain
incomplete, double touches ambiguous. Counts are not trading returns.

Forecasts created after the first target minute has completed, or without a
creation timestamp, are displayed but excluded from prospective summary scores.
Forecasts generated partway into that first minute remain included; this is an
availability screen, not a latency-adjusted execution test. Overlapping forecasts
are not independent observations. Watched sessions are explored development,
not untouched confirmation, regardless of an earlier prospective study plan.

New five-minute forecasts save `forward_context` in `forecasts.jsonl`: completed
session candle HLC3 VWAP approximation and 200 completed regular-session minute
closes, including validated prior history. Context is assembled before inference;
old forecasts retain missing context, including cached forecasts created earlier.
No Kronos inputs or trained weights are changed.

Derived review snapshots are refreshed under `data/kronos_lab/forward_review/`.
They include daily totals and latest 100 rows; full forecasts and candles remain
in their existing stores. Actuals reflect the latest saved provider candles and
may change with provider corrections; these are review snapshots, not immutable
first-arrival outcome labels. Six focused scoring/context/warmup tests pass.
