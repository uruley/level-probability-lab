# Bull / bear probability summary

## Correction: paired comparisons (September 23)

The earlier "95% session intervals" below are percentiles of individual
session scores, NOT confidence intervals. They cannot establish uncertainty
in an engine's improvement. Superseding artifact:
`data/bull_bear_truth_v1/baseline_probability_summary_v2.json`.

V2 resamples 21 paired June sessions with replacement, 5,000 replicates,
seed 20260923. It retains all origins in each sampled session and computes
the pooled per-origin engine-minus-baseline loss difference. Negative favors
Kronos. May frequencies remain fixed; no refitting within the bootstrap.
Base and Small must have identical origins, split, session and outcome labels.
Brier now uses raw probabilities; only log loss clips at 1e-6 and renormalizes.
Old misleading fields are renamed `session_*_percentiles_2_5_97_5` in v2.

| June engine vs May climatology | Brier delta (95% CI) | Log loss delta (95% CI) |
| --- | --- | --- |
| Base | -0.054920 [-0.096987, -0.020918] | +0.413688 [+0.208566, +0.626901] |
| Small | -0.056875 [-0.099303, -0.022230] | +0.361365 [+0.198761, +0.532066] |

Both beat always-neutral persistence on both metrics. Relative to climatology,
the evidence is mixed: better Brier, worse log loss. Log loss penalizes assigning
very low mass to realized outcomes. This does not establish calibrated market
probabilities. May/June have been repeatedly inspected in prior research;
"validation" is the archived split label, not a claim of a fresh untouched test.
Intervals are conditional on this fixed study, not multiple-testing adjusted.
No July data or additional model calls were used. Analogue multiclass comparison
is still pending and no Jev accuracy claim follows from the one-origin pilot.

The archived sampled-path data available in the replay folders currently covers
one complete August development session for this contract: **266 Kronos Small
origins on 2026-08-14**. The stored path frequency gives an empirical bull,
neutral and bear distribution for each origin, using the fixed +/-0.10% close
return threshold at +5 minutes.

The result is saved in `data/bull_bear_truth_v1/probability_summary.json`:
Brier 0.008478 and log loss 0.060796. The outcome prevalence in this slice is
265 neutral and 1 bear, with no bull outcomes. There is no session bootstrap
interval because one session is not enough. The values are empirical sampled
path frequencies, explicitly **not calibrated market probabilities**.

This is a wiring check, not evidence of skill. The older 21-session score ledger
does not retain compatible raw sampled paths for every origin, so it cannot be
silently converted into multiclass probabilities. The next bounded task is to
use the frozen `data/kronos_baseline_v1` export, which contains compatible paths
for 2,214 May/June origins for each of Kronos Base and Small (41 sessions). Its
descriptive five-minute scores are Brier 0.345711 / log loss 1.186737 for Base
and Brier 0.342804 / log loss 1.122780 for Small. July was not read. These
values remain empirical path frequencies, not calibrated market probabilities;
split-level comparison against fixed climatology and persistence is now also
recorded. On the 21-session validation split, Base scored Brier 0.431119 and
Small 0.429164; development-only climatology scored 0.486040 and neutral
persistence 0.576718. These descriptive results do not establish calibrated
probabilities or trading skill. Session-level 95% intervals are now included
in the JSON artifact; for validation Brier they are Base [0.060326, 0.804118],
Small [0.058104, 0.787497], development climatology [0.072690, 1.041260],
and neutral persistence [0.055555, 1.277773]. The wide intervals show why
this remains exploratory. No July, Jev, order flow or UI changes are included.
