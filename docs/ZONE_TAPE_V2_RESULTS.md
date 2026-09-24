# June tape resolution and grouped encounters

1,065 touched candle records checked using the acquired Nasdaq receive-time
tape, retaining original inputs/outcomes. 3,587 selected minutes reconcile;
154 do not pass the full audit. Any affected full event window stays incomplete,
even when an early outcome might otherwise be visible. No July analysis or API.

Record counts: 554 rejection, 390 continuation, 116 incomplete, 3 gap-over-zone,
2 ambiguous. These overlap substantially and must not be treated as trades.

Grouping was frozen before tape outcomes: within each date and level family,
overlapping [origin, touch-minute + 15 minutes) windows form connected groups.
The earliest origin represents each group, even if incomplete. This conservative
rule can merge distinct revisits; it reduces duplication but does not establish
independence or prove that all members are one physical encounter.

| Level | Groups | Rejection | Continuation | Incomplete | Rejection fraction among resolved | Descriptive 95% session bootstrap |
|---|---:|---:|---:|---:|---:|---:|
| One-minute SMA200 | 27 | 17 | 2 | 8 | 89.5% (17/19) | 75–100% |
| Session VWAP | 15 | 7 | 8 | 0 | 46.7% (7/15) | 19.0–75% |
| Previous daily high | 6 | 5 | 1 | 0 | 83.3% (5/6) | 33.3–100% |
| Previous daily low | 5 | 1 | 2 | 2 | 33.3% (1/3) | 0–100% |
| Hourly SMA20 | 12 | 10 | 1 | 1 | 90.9% (10/11) | 73.3–100% |

Intervals resample all 21 sessions with replacement, 5,000 draws, seed 42.
Zero-denominator draws excluded. Small samples, missing windows, grouping choice,
and previously explored June data limit these descriptive intervals. No matched
baseline, execution model, multiplicity adjustment or untouched confirmation.
These percentages describe frozen response barriers, NOT trading win rates or
calibrated probabilities. No indicator or model promoted.

Artifacts: `data/zone_response_v2/tape_manifest.json`, `tape_outcomes.json`,
`encounters.json`, `tape_summary.json`. Optimized tape resolution matches the
original resolver on 100 deterministic randomized tied-timestamp cases.

Chart SMA200 now receives 199 validated preceding RTH minutes from existing
local warmup. Incomplete history leaves it unavailable; no new downloads.
VWAP still resets at open. Nine zone tests, four opening/warmup tests and chart
checks pass. Next research task: audit missing tape minutes and predeclare an
unchanged comparison/confirmation sample before treating SMA200 as an edge.
