# First candidate-area pilot

Implemented `zone_response.observe` and offline builder `scripts/build_zone_response.py`.
Audited existing trade-feature file hash and acceptance flag; verified saved
context hashes and level availability. Selected three fixed levels on each
of twenty May sessions without outcome filtering. Inputs and outcomes are
separate immutable artifacts under `data/zone_response_v1/`. Repeated build
matched the frozen records. Four focused tests pass (no touch vs missing,
rejection and volume, ambiguous ordering, continuation).

Observed: 60 candidates, 56 no-touch, four ambiguous touch-minute responses.
No resolved rejection/continuation rate is estimable from this pilot. The fixed
11:30 origin and levels often far from price make this a sparse experiment.
Do not broaden bands or change barriers based on these outcomes. Trade volume
is whole-minute Nasdaq executed shares, NOT volume at the candidate price.

Standalone visual ledger: `data/zone_response_v1/index.html`, all 60 events,
observed minute-close paths, frozen level and response barriers, touch-minute
shares and prior-20-minute volume ratio. This is separate from the live lab;
no server/chart changes, Jev calls, purchases or training were made.

Next bounded work: inspect already acquired raw trade sequences for the four
ambiguous events and assess whether receive/event time and coverage can resolve
touch-before-response ordering. Preserve the candle-only labels and add a
separate tape-resolved field if justified. No hindsight threshold search.
