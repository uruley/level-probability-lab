# QQQ bull / neutral / bear truth-set contract v1

Stage 1 is offline only. This is a new label family, separate from legacy
upper_first/lower_first/neither, Scout labels, and binary up-event scores.

Entry points: bull_bear_truth.snapshot, score, persist, replay. Inputs are lists
of records with symbol=QQQ, source_id, timezone-aware bar_start, bar_end,
available_at, OHLCV and optional corrected flag. Origins and decision cutoffs
are explicit. No provider, model, UI, or network adapter is invoked.

Origin is the completed one-minute bar END in UTC. Decision cutoff must be
at or after origin but before the first target closes. The exact input window
is same-session, contiguous and fully available by that cutoff (default one
bar; lookback is explicit). A corrected input or multiple available versions
blocks the origin. Future input mutations do not change snapshot identity.

The five target starts are origin through origin+4 minutes. Outcome maturation
is origin+5 minutes. All five must be in the same NYSE RTH session, including
early-close rules. No skipping missing minutes or crossing overnight closures.
Label spec close_return_pm_10bp_v1: p5 > p0*1.001 is bull; p5 < p0*0.999 is
bear; all other values, including both boundaries, are neutral. Decimal price
comparisons avoid floating-point boundary drift. Pending or unscorable records
have null class/endpoint/return. Invalid, missing, delayed, duplicate or corrected
future bars do not produce a class. A visible change to the origin also prevents
scoring. Vendor corrections must be provided as marked or multiple versions;
the module cannot discover corrections a supplier does not expose.

Callers must specify experiment_id, source, price_policy, availability_policy
and code_version. Historical bar-end availability is an explicit assumption,
not a reconstruction of original vendor receipt times. Do not silently treat
Webull and Nasdaq prices as interchangeable. source_id identifies a source
record/version; snapshot SHA256 covers full selected values and provenance.

Persistence reuses ForecastStore in dedicated snapshots.jsonl/outcomes.jsonl.
Content-addressed IDs make exact reruns idempotent. Outcomes include scoring
time, expected timestamps, available future records and quality reasons. Later
scoring/correction snapshots append; earlier outcomes are never rewritten.
Single writer only, matching the existing store's concurrency limitations.
Consumers must select the appropriate outcome as-of/version, not count appended
snapshots as independent forecasts. A malformed origin raises ValueError;
a missing outcome is recorded as unscorable after maturity.

This implements the truth set, not an engine prediction ledger or probability
calibration. No probabilities are produced. Stage 2 will attach same-origin
baselines/Kronos distributions after this contract is accepted. Jev and flow
remain deferred. July sealed studies are not read or modified.

Offline test command:
`python -m pytest tests/test_bull_bear_truth.py -q -p no:cacheprovider`
