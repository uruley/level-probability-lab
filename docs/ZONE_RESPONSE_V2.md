# Candidate-zone expansion v2

Frozen specification before evaluating v2: use every archived June 2026 origin
in location_evaluation_v1, deduplicated by date/as_of. June has been explored
before: this is descriptive development, not a held-out test. Preserve v1.

Five fixed candidates: previous daily high/low, hourly SMA20, regular-session
VWAP, and SMA of the last 200 completed regular-session one-minute closes
(carry across sessions, exclude extended hours). Use the exchange minute grid;
missing or ineligible inputs make a level unavailable. VWAP resets at 09:30
New York and uses audited Nasdaq receive-time trade dollars reconstructed from
minute VWAP and shares. This is venue-only VWAP, not consolidated VWAP.

Freeze levels at origin, never update them during observation. Retain v1's
0.1R zone, 0.5R barriers, 60-minute touch search and 15-minute response window.
Keep unavailable, already-inside, incomplete, ambiguous and unresolved separate.
No tuning, July reads, paid calls, training, fills or probability claims.
Overlapping origins are not independent trades. Report counts by level and
session count; do not interpret a percentage as a market probability.

Chart overlays are separate: candle VWAP uses cumulative HLC3 times volume,
explicitly approximate; SMA200 uses available completed one-minute history.
If fewer than 200 bars are loaded it is unavailable, never shortened.
