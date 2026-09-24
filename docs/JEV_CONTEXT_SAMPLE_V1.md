# Jev context comparison: offline preparation

## Completed comparison

User authorized execution; all 80 requests validated, with zero missing replies.
`scripts/test_jev_context.py` replays from cache without network by default.
`data/jev_context_sample_v1/execution.json` records subsequent authorization,
code/manifest hashes, pinned jev-1.13.0 and verified pricing. Original selection
manifest stays unchanged. Raw replies and `report.json` are saved alongside it.
Cached rerun reproduced results; 23 focused tests passed.

| Engine | Brier (lower better) | Log loss (lower better) |
| --- | --- | --- |
| Kronos Base | 0.228720 | 0.703889 |
| Jev, Kronos summary only | 0.244545 | 1.001762 |
| Jev, summary plus context | 0.256446 | 0.767812 |
| May climatology (in-sample) | 0.266164 | 0.525091 |
| Neutral persistence | 0.300000 | 2.072328 |

Context minus no-context paired session-bootstrap differences: Brier +0.011901
(95% interval -0.010545 to +0.049613); log loss -0.233950 (-0.705646 to
+0.012501). Both cross zero. Context minus Kronos: Brier +0.027726
(-0.026521 to +0.098161), log loss +0.063923 (-0.051993 to +0.217602).
No reliable improvement established, and no model promotion. Forty origins
include 34 neutral, four bull, two bear outcomes across twenty previously
explored May sessions. Confidence intervals are exploratory, not evidence of
calibration or trading returns. Do not tune prompts to these outcomes.

Reported usage: 134,600 input tokens. At the rechecked official rate of
$0.042 per million input tokens (output free), estimated charge $0.0056532,
not an account billing receipt. Source: https://docs.typesafe.ai/models.
The $0.25 cap and eighty-request limit were respected. No July access,
continuous API calls or live chart changes were made.

Forty archived Base origins are frozen in `data/jev_context_sample_v1/manifest.json`:
zero-based origins 0 and 27 for each of the twenty May 2026 sessions.
Selection is chronological, with no outcomes read or filtering by proximity.
Previously inspected May data is development evidence, not a new final test.

Each origin has matching compact packages with and without market context.
Context includes hourly/daily SMA 5/10/20/50/100/200, BB20 lower/upper,
previous-day high/low, session high/low so far, and signed distance in basis
points (price minus level). All twenty levels are available for all forty
origins. Source is `location_evaluation_v1/prediction_contexts.jsonl`.

Audit verifies context content hash, archived forecast byte hash, input hash,
origin, reference close, decision cutoff, history-end and level timestamps,
and recalculated signed distances. No level timestamp exceeds cutoff.
The historical builder uses only completed bars, RTH hours anchored at open,
and completed daily bars; this audit does not prove live receipt latency or
independently rebuild all indicators from raw source data. No outcomes are
included in either package. Order flow remains unavailable.

Run `scripts/freeze_jev_context.py` to reproduce; immutable artifacts reject
changes. Repeated run matched byte-for-byte. Eight focused tests passed,
including future-level/history, reference mismatch and hash rejection.

Proposed experiment: pinned Jev 1.13.0, eighty total calls, $0.25 cap,
no retries after uncertain charges. Recheck official pricing before execution.
At the previously verified $0.042/M input rate, even eighty 65,536-token
requests total $0.22020096. No new batch spending authorized here; network
disabled. Compare paired context minus no-context Brier and log loss, plus
Kronos reference, after freezing all replies. Retain raw and normalized Jev
scores and report exclusions. No prompt selection, calibration or live-chart
promotion from this development sample; analogue comparison remains pending.
