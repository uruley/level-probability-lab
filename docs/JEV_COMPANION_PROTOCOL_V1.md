# Jev companion protocol v1

## Ten-origin test completed

User approved testing the batch. `scripts/test_jev_sample.py --allow-network`
completed all ten pinned jev-1.13.0 requests, then joined outcomes. The default
command (without the flag) replayed the cached responses successfully.
Execution configuration, source/package hashes, raw responses and report are
saved in `data/jev_sample_v1/`. The frozen selection manifest retains its
original proposal status; `execution.json` records the subsequent approval.

Pricing verified at https://docs.typesafe.ai/models: $0.042/million input
tokens, output free, 64k context. Conservative ten-request full-context bound
was $0.02752512, under $0.25. Reported input usage 7,942 tokens implies
$0.000333564 at this rate, not a billing receipt. Ten distinct per-origin
reservations prevent automatic repeated charges; all responses validated.

| Engine | Brier | Log loss |
| --- | --- | --- |
| Jev | 0.386680 | 1.762753 |
| Kronos Base | 0.326080 | 1.654979 |
| May climatology | 0.344498 | 0.644367 |
| Neutral persistence | 0.400000 | 2.763104 |

Lower is better. Jev did not improve either metric over Kronos or climatology
in this tiny sample (8 neutral, 2 bull, 0 bear). This verifies integration,
not predictive value. All 18 relevant offline tests passed. The report includes
paired session comparisons, but ten exposed development origins do not support
promotion or calibration; analogue comparison remains unavailable. No live
chart polling or automatic Jev calls are enabled.

## Frozen ten-session sample

`scripts/freeze_jev_sample.py` froze ten compact packages and a manifest under
`data/jev_sample_v1/`. Selection: earliest archived Base origin on each of the
first ten May sessions after May 1, excluding the already examined pilot.
Dates are May 4–15, cutoff 15:30 UTC each day. Selection reads no outcomes.
The rerun verified byte-identical packages and manifest; changes fail closed.

Proposed limits: ten requests, $0.25 total. This is a proposal, not a verified
quote or a provider-side cap. Approved batch spending remains zero; network is
disabled until pricing/cost bounding and batch authorization are resolved.
Pin jev-1.13.0; preserve raw responses, do not retry uncertain requests, and join
outcomes only after all responses are frozen. Report failures and exclusions.
This is a feasibility sample from previously explored development data, not
enough to calibrate or establish predictive skill. Compatible analogue
distributions remain unavailable; do not fabricate them or claim comparison.

## Offline compact package

`scripts/prepare_jev_compact.py` builds `data/jev_compact_v1/package.json`
from the same May 1 archived forecast, without keys or network access.
It contains the decision cutoff and final target close time, current close,
fixed label thresholds, five close-return quantile triplets and final class
frequencies. It allowlists fields rather than copying outcomes from the archive.
Market-location context and order flow are explicitly unavailable.
OHLC ordering failures are counted; only finite positive closes are summarized,
and this package makes no high/low range claim. It does not repair saved paths.

Compact serialized state is 795 bytes vs 9,948 for the previous state, a 92.0%
byte reduction. This is not a token measurement or a cost quote. A source
reference and deterministic package hash are saved in the manifest. This schema
has not been sent to Jev and is not yet wired to a new real-request runner.
The saved pilot and one-request reservation remain intact.

## Integration status, September 23

Update: after explicit user approval, one real May 1 request succeeded with
model `jev-1.13.0`. Raw scores: bull 0.10, neutral 0.56, bear 0.33; confidence
0.35; usage 10,064 input / 41 output tokens. Dollar charge is not reported.
Response is preserved in `data/jev_pilot_v1/`; replay uses no network.
The observed sum was 0.99. The provider adapter now accepts only a 0.015
rounding envelope (three two-decimal scores), preserves the raw values and
explicitly divides by the observed sum for a normalized distribution.
This is an engineering accommodation, not calibration. Larger discrepancies
are rejected. Twelve offline tests pass. This supersedes the pending approval
status below. The pilot is working; continuous chart integration is not enabled.

The adapter now reads the official `answers.move_5m` response envelope,
validates numeric scores summing to one, preserves model version, confidence
and usage, and saves the response before parsing. Confidence is not a win rate.
Reference: https://docs.typesafe.ai/primitives/choice

`scripts/run_jev_pilot.py` prepares exactly the archived May 1 15:29 UTC
bar-start Base forecast (decision cutoff 15:30 UTC). It sends origin price,
25 five-minute sampled OHLC paths, derived medians/ranges, target timestamps
and source input hash. It does not load outcome labels. Without
`--allow-network`, only an existing cached response can be replayed.
The durable `data/jev_pilot_v1/attempt.json` reservation permits one request,
including across process restarts; an uncertain failure blocks another call.
Responses are cached for free offline reparsing. There is no provider-enforced
dollar cap; actual cost is unknown, so a request limit must not be described as
a dollar cap. Earlier calls were not cached and their cost is unknown.

Nine offline tests pass. Automatic approval review blocked the planned real
archived-input pilot pending explicit approval to send this package to TypeSafe
and consume credits. No real call was made in this repair step. The integration
is tested offline, not yet verified end-to-end with this historical package.

This document defines the interface for a later Jev/LLM comparison. It is a
protocol only; no Jev calls or paid APIs are made by this step.

## Frozen input

One row is created only when a five-minute Kronos forecast has a complete,
point-in-time input package. The package contains the forecast origin and
session, origin close, five sampled-path close distributions, the Kronos
median/range, and the fixed bull/neutral/bear label definition from
`BULL_BEAR_TRUTH_V1.md`. Optional chart-location fields may be included only
when they were available at the origin. Future candles, revealed outcomes,
order flow, and July data are excluded from Jev's input.

## Required output

Jev must return structured JSON with `bull`, `neutral`, and `bear` numeric
scores, each in [0, 1], plus a short reason and an `input_complete` flag. The
three scores are treated as model scores until calibration is separately
demonstrated; they must never be described as market probabilities by default.
Malformed, missing, or non-finite output is recorded as unavailable and is not
silently converted to neutral.

## Evaluation

Run Jev on a predeclared May/June development/validation origin list. Freeze
the prompt, model identifier, temperature, seed (if supported), input schema,
and parser before scoring. Score Jev against the same five-minute labels as
Kronos with multiclass Brier and log loss, by session and split. Compare with
neutral persistence, development climatology, Kronos Base, and Kronos Small.
Do not fit thresholds, calibrate scores, or select a trade rule using July.

The first run should be an offline fixture test and a small development-only
sample to verify deterministic packaging and parser behavior. A full Jev
evaluation requires an explicit model/access decision and remains separate
from Kronos inference.
