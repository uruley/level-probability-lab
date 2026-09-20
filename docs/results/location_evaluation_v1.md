# Kronos forecast location - development results

Completed 2026-09-19. **We have not established that confluence improves Kronos forecasts.** The fixed confluence rule found only five origins across two sessions. This is insufficient for a dependable estimate or Scout training decision.

## Scope and integrity

- 2,214 archived Kronos Base forecasts across 41 May/June sessions; 54 per session, five-minute cadence. No missing origins.
- 13,284 origin/ratio/window rows, with four direction strategies evaluated per row. No new model inference or fitting.
- All prediction input hashes and candle-source hash verified. All 2,214 context hashes and cutoff timestamps audited.
- Replay observer matched at the first origin of every session for all six ratio/window combinations. Independently verified 984 late-session direction outcomes.
- No missing outcomes or neutral Kronos setups in this run. July forecasts/outcomes were not accessed; July remains sealed.
- These are development results, not a fresh held-out test or evidence of trading returns.

## Primary comparison: confluence versus elsewhere

Confluence requires an hourly/daily SMA pair each within 0.5R of price and within 0.5R of one another. R is the frozen ATR14 from the 120-minute input window. This is a narrow absolute-price condition: five matches (0.23% of origins). The other 2,209 origins had no confluence; no unknown groups.

| Deadline | Reward:risk | Confluence target first | No-confluence target first | No-confluence excess over fair coin (95% interval) |
|---|---|---|---|---|
| 5 minutes | 1:1 | 4/5 (80.0%) | 977/2209 (44.2%) | +0.86 pp [-1.04, +2.60] pp |
| 5 minutes | 2:1 | 2/5 (40.0%) | 380/2209 (17.2%) | +1.36 pp [+0.16, +2.49] pp |
| 5 minutes | 3:1 | 0/5 (0.0%) | 122/2209 (5.5%) | +0.72 pp [+0.07, +1.36] pp |
| Up to 60 minutes / close | 1:1 | 5/5 (100.0%) | 1123/2209 (50.8%) | +1.29 pp [-0.84, +3.28] pp |
| Up to 60 minutes / close | 2:1 | 3/5 (60.0%) | 767/2209 (34.7%) | +1.58 pp [-0.34, +3.50] pp |
| Up to 60 minutes / close | 3:1 | 3/5 (60.0%) | 607/2209 (27.5%) | +2.40 pp [+0.41, +4.36] pp |

**Do not interpret 4/5 or 5/5 as an established 80% or 100% setup.** There was just one confluence origin in May and four in June, concentrated on one session each. Confluence-versus-away bootstrap intervals are withheld: only 1,744/2,000 whole-session bootstrap draws contain both groups.

Some no-confluence comparisons have unadjusted intervals above zero. Those describe modest direction differences away from the chosen zones, not a confluence advantage. There are many exploratory comparisons; no strategy or model is promoted.

## Secondary location descriptions: five minutes, 1:1

These overlapping groups were specified before the run. Near means within 0.5R of at least one level. Bollinger proximity refers to an upper/lower boundary, not the middle average.

| Location | Origins / sessions | Kronos target first | Fair-coin target first | Paired excess (95% interval) |
|---|---|---|---|---|
| near hourly sma | 191 / 34 | 42.4% | 43.5% | -1.05 pp [-6.68, +4.60] pp |
| near daily sma | 49 / 12 | 36.7% | 38.8% | -2.04 pp [-13.64, +8.16] pp |
| near hourly bb | 42 / 14 | 47.6% | 40.5% | +7.14 pp [-5.56, +19.00] pp |
| near daily bb | 16 / 6 | 62.5% | 46.9% | +15.62 pp [-15.76, +35.94] pp |

All four pooled secondary excess intervals include zero. The daily-band percentage is based on only 16 origins across six sessions; it is not strong evidence of predictive value.

| Location | May: target-first / origins | June: target-first / origins |
|---|---|---|
| confluence | 100.0% / 1 | 75.0% / 4 |
| no confluence | 43.7% / 1079 | 44.8% / 1130 |
| near hourly sma | 43.2% / 74 | 41.9% / 117 |
| near daily sma | 23.1% / 26 | 52.2% / 23 |
| near hourly bb | 60.0% / 20 | 36.4% / 22 |
| near daily bb | 61.5% / 13 | 66.7% / 3 |

## Matched direction controls: no confluence, five minutes, 1:1

| Direction | Target first | Stop first | Neither | Ambiguous |
|---|---|---|---|---|
| kronos | 44.2% (977) | 42.5% (939) | 12.5% (277) | 0.7% (16) |
| always up | 43.6% (963) | 43.1% (953) | 12.5% (277) | 0.7% (16) |
| always down | 43.1% (953) | 43.6% (963) | 12.5% (277) | 0.7% (16) |
| momentum5 | 43.7% (960) | 43.0% (945) | 12.6% (277) | 0.7% (16) |

The fair-coin control is the exact average of always-up and always-down outcomes at the same origins, reference prices, risk distance, reward ratio and deadlines. It is not a flat-price forecast and does not assume a 50% target-hit rate. Recent-direction control uses the previous five-minute close change, with neutral excluded and counted.

## Scoring and uncertainty

Target-first percentages divide by all complete outcomes, including neither/expired and ambiguous. They are not target/(target+stop). The extended deadline is capped at the regular-session close. Same-minute dual touches remain ambiguous. Touch minutes, targets, stops, coverage and each control are in outcomes.csv.

Intervals resample all sessions with their overlapping origins together (2,000 draws, fixed seed). Zero-member sessions remain in the sampling universe; draws lacking a denominator are invalid. At least two contributing sessions and 1,900 valid draws are required to print an interval. Sparse-group intervals remain fragile even when available. Location associations are not causal; volatility, time of day and trend can differ between groups.

## What follows

Keep this result and its fixed rule. Do not retrain Scout on five confluence examples or widen the threshold until a favorable score appears. A next version should predeclare broader location categories or additional development sessions, verify event counts before examining outcomes, and evaluate stability across time. More independent examples are needed to assess the strict confluence hypothesis.

## Artifacts and correction audit

- protocol.md: frozen rules. prediction_contexts.jsonl: context and setup ledger written before scoring each origin.
- outcomes.csv: all outcomes. summary.csv and comparisons.csv: May, June and pooled results for every ratio/window/group/control.
- report.json, verification.json and manifest.json: structured results, independent checks and hashes.
- initial_* files are superseded audit copies. The initial group-rate bootstrap conditioned on sessions containing a group. Before delivery, this was corrected to sample the full session universe, as the protocol specifies. Sparse confluence intervals are therefore withheld. No input records, outcomes, thresholds or point estimates changed.
