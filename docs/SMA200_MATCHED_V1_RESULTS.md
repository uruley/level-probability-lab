# SMA200 matched comparison: no convincing added value yet

Completed 2026-09-23 using existing June data only. Rules frozen in
`SMA200_MATCHED_V1.md`; original zone and encounter results preserved.

## Incomplete encounter audit

All eight incomplete SMA200 representatives extend beyond the 16:00 New York
regular close. Their 75 missing requested minutes are all after close. Raw
Nasdaq tape reconciles with audited OHLCV/trade counts for all 330 pre-close
minutes; no pre-close failures. These are session-end truncations, not evidence
of an intraday feed outage. The original full-window rule leaves them incomplete;
no selective relabeling to improve the headline.

## Fixed matched comparison

Selected 63 origins on a 75-minute schedule, with a full observation horizon
inside the regular session. Matched 57 to different-session hypothetical levels
using past-only time, risk, approach direction and exact normalized starting
distance. Six cases have no qualifying match; calipers were not relaxed.
Controls are at least 1R from their actual SMA200. All touched windows use
the same audited tape-resolution rules.

| Outcome | SMA200 candidates | Matched control candidates |
|---|---:|---:|
| Rejection | 12 | 11 |
| Continuation | 9 | 7 |
| No touch | 35 | 37 |
| Already inside | 1 | 1 |
| Ambiguous | 0 | 1 |
| Incomplete | 0 | 0 |
| Total | 57 | 57 |

Primary descriptive rejection frequency: 12/57 (21.1%) versus 11/57 (19.3%),
a +1.75 percentage-point difference. This combines reaching the level and then
rejecting; it is not conditional bounce probability or trading win rate.
The ambiguous control remains ambiguous; if it rejected, the difference would
be zero. There are six pairs with rejection only in the SMA arm, five only in
the control arm, and 46 with no difference in rejection indicator.

This is a different, less selected sample from the earlier 17/19 touched-group
fraction. Do not compare those percentages as estimates of the same quantity.
Shared sessions across pairs, prior June exploration, arbitrary matching choices
and small counts prevent a claim of edge. No independent-binomial confidence
interval reported; no new threshold search or Scout training justified.

## Confirmation status

No existing local period has been certified as untouched. May/June and August
have documented exposure; July is sealed; September through the 23rd includes
live/replay inspection. A prospective plan reserves 20 regular sessions from
September 24 through October 21, 2026, contingent on data coverage and a
no-peeking/exposure log. It does not collect data, enable a feed, spend money,
or certify future data quality. Any inspected session loses untouched status;
do not silently replace it. Final confirmation has NOT run because these
sessions have not occurred.

Artifacts: `data/sma200_matched_v1/` includes frozen matched inputs, hashes,
outcomes, summary, incomplete audits and confirmation plan. The development
run was repeated and matched every immutable artifact. Eleven focused tests
pass, including deterministic matching, unchanged distance/direction and tape
ordering parity. No paid calls or July outcomes accessed.
