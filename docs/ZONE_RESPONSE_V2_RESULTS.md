# June candidate-zone expansion

Completed 2026-09-23: 1,134 archived origins across 21 June sessions; 5,670
frozen candidate records. Protocol: `ZONE_RESPONSE_V2.md`. Artifacts in
`data/zone_response_v2/`: inputs, outcomes, manifest, summary. Source audit
and context hashes verified. May pilot artifacts preserved; July untouched.

| Level | No touch | Already inside | Rejection | Continuation | Ambiguous | Incomplete |
|---|---:|---:|---:|---:|---:|---:|
| Session VWAP | 639 | 12 | 7 | 12 | 277 | 187 |
| One-minute SMA200 | 575 | 8 | 11 | 5 | 408 | 127 |
| Hourly SMA20 | 742 | 7 | 8 | 1 | 164 | 212 |
| Previous daily high | 818 | 2 | 1 | 7 | 85 | 221 |
| Previous daily low | 849 | 0 | 0 | 0 | 79 | 206 |

Each row totals 1,134. Missing coverage/session truncation remains incomplete.
Do not compute a success rate from the small unambiguous subset: intraminute
ordering is unknown for most touches. Origins overlap, and June was previously
explored. No edge, trading returns, or calibrated probability established.
Next bounded measurement: resolve ambiguous events from the acquired tape,
retaining original candle labels and auditing each extracted window.

Chart: added default-on Session VWAP (approx.) and dedicated 1m SMA200 controls
to the main chart, independent of the other indicator timeframe selector.
VWAP uses completed one-minute HLC3 weighted by volume, resetting at the RTH
open. It is an approximation and not the study's audited trade VWAP. Chart
SMA200 needs 200 loaded completed minute bars; prior-session warmup is not
currently exposed to this overlay. Study SMA200 carries across RTH sessions
on an exchange calendar grid. Missing inputs are never skipped or shortened.

Verification: eight Python tests pass, chart formula/as-of/gap tests pass,
and running UI verified with both controls checked and VWAP value displayed.
No paid calls, new data downloads, model training or changes to Kronos inputs.
