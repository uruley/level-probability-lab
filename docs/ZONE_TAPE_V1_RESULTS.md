# Trade-sequence resolution of the four ambiguous events

Existing raw DBN matched the accepted audit SHA256. Only four May receive-time
windows were extracted, with sequential reading stopped before later dates.
All 98 event-window minutes reconciled to audited OHLC, volume and trade count.
Zero event-time inversions within the selected windows. Ordering uses receive
timestamps; equal-timestamp touch/barrier events would remain ambiguous.

| Date / frozen level | Tape response | Seconds after touch | Shares traded inside zone before resolution |
| --- | --- | ---: | ---: |
| May 7 / previous high | Rejection | 5.280 | 31 |
| May 13 / previous high | Continuation | 0.837 | 40 |
| May 15 / hourly SMA20 | Continuation | 12.261 | 1,463 |
| May 19 / previous low | Continuation | 20.330 | 1,221 |

First touch is the first print inside the original +/-0.1R zone after cutoff.
Subsequent first +/-0.5R barrier determines response. Prices beyond a barrier
before touch do not count. Crossing a zone without an inside print is not an
assumed fill. Existing first-touch minute and 15-minute expiry are unchanged.

Shares are executed Nasdaq-only volume within the frozen zone from first
touch through resolution (inclusive timestamp groups), not resting liquidity,
consolidated volume, aggressor imbalance, or fillable size. Subsecond outcomes
cannot establish that a hypothetical entry would have executed profitably.
No fees/spread/latency simulation or probability estimate is provided.

Original candle labels remain ambiguous and byte-identical. Separate results:
`data/zone_response_v1/tape_outcomes.json`; extracted records:
`data/zone_response_v1/selected_tape.parquet`. Original 56 no-touch candidates
remain in the denominator; four resolved events do not justify a zone rule.
Six focused ordering/label tests pass. No API calls, purchases, July analysis,
training, or threshold changes. Repeat run matched frozen results.
