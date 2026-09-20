# August location replication — v3

1,134 frozen Kronos Base forecasts across all 21 August 2026 regular sessions. This is additional development evidence: August had already been inspected. It is not an untouched final test.

## Findings

- Overall five-minute 1:1: 521/1,134 target-first (45.9%) versus 43.8% matched coin. Excess +2.2 percentage points, 95% session interval [-0.5, +4.8]; no clear overall advantage.
- Hourly SMA distance >0.5–1R: 49/86 target-first (57.0%), versus 45.9% coin, across 18 sessions. Excess +11.0 points [1.1, 20.0]. This is an exploratory positive signal, not a stable filter: May was 40.6%, June 46.2%, and the August excess difference versus >2R still includes zero [-0.3, 19.0].
- Strict confluence remains sparse: 2/8 (25.0%) in August versus 4/5 (80.0%) in May/June. Broader >0.5–1R confluence has an exploratory positive excess but only 15 origins across six sessions, below the cross-month coverage requirement. Neither supports promotion.
- The earlier negative >1–2R hourly-SMA association did not repeat clearly in August. No August origins were within 2R of daily Bollinger boundaries, so those near bands received no additional evidence.
- Extended 2:1 shows a secondary overall excess of +2.7 points [0.1, 5.4]. This is among many secondary comparisons, not confirmation of a location effect or trading profitability.

Keep these categories fixed. Preserve the hourly >0.5–1R observation as a candidate for future chronological confirmation; do not widen thresholds or turn the best August cell into a Scout rule. The next confirmatory period requires a prior-exposure audit and a frozen protocol before inspecting outcomes.

Same model, 120-bar inputs, 25 paths, seed 42, five-minute forecast cadence, indicators, ATR14 risk, distance bands, and target/stop scoring as May/June. Forecast cutoffs run from 11:30 a.m. through 3:55 p.m. New York time, after the initial 120-minute lookback; this does not test the opening two hours. No training, data purchase, or changes to the replay. July forecast and outcome archives were not evaluated; completed July candles supply past indicator warmup only.

## Overall August outcomes

Percentages use all completed setups, including neither/expired and same-minute ambiguous outcomes. Fair coin chooses up/down with equal probability at the exact same origin, risk, ratio and deadline; its target-first rate is not assumed to be 50%.

| Window | Reward:risk | Complete | Target first | Stop first | Neither/expired | Ambiguous | Matched coin | Kronos minus coin (95% session interval) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 5 minutes | 1:1 | 1134 | 45.9% (521) | 41.6% (472) | 11.9% (135) | 0.5% (6) | 43.8% | +2.2 pp [-0.5, +4.8] |
| 5 minutes | 2:1 | 1134 | 17.7% (201) | 46.0% (522) | 36.2% (410) | 0.1% (1) | 16.6% | +1.1 pp [-0.7, +3.0] |
| 5 minutes | 3:1 | 1134 | 5.9% (67) | 46.6% (529) | 47.4% (537) | 0.1% (1) | 5.8% | +0.1 pp [-0.8, +1.1] |
| Up to 60/session close | 1:1 | 1134 | 52.3% (593) | 47.2% (535) | 0.0% (0) | 0.5% (6) | 49.7% | +2.6 pp [-0.5, +5.7] |
| Up to 60/session close | 2:1 | 1134 | 35.6% (404) | 64.1% (727) | 0.2% (2) | 0.1% (1) | 32.9% | +2.7 pp [+0.1, +5.4] |
| Up to 60/session close | 3:1 | 1134 | 27.8% (315) | 71.4% (810) | 0.7% (8) | 0.1% (1) | 25.0% | +2.7 pp [-0.2, +5.8] |

## Primary view: five-minute 1:1 by location

Distances use the original frozen one-minute ATR14 (R). “Near” does not change the Kronos inputs. The same forecast can appear in different families; bands within each family are disjoint. Empty groups remain visible.

| Family | Distance | August origins / sessions | May/June target rate | August target rate | August coin | August excess (95% interval) |
|---|---|---:|---:|---:|---:|---|
| hourly sma | ≤0.5R | 103 / 19 | 42.4% | 45.6% | 43.7% | +1.9 pp [-6.6, +10.4] |
| hourly sma | >0.5–1R | 86 / 18 | 43.9% | 57.0% | 45.9% | +11.0 pp [+1.1, +20.0] |
| hourly sma | >1–2R | 175 / 20 | 38.2% | 45.7% | 44.6% | +1.1 pp [-3.9, +6.9] |
| hourly sma | >2R | 770 / 21 | 45.7% | 44.8% | 43.4% | +1.4 pp [-1.9, +4.7] |
| hourly sma | Unknown | 0 / 0 | — | — | — | — |
| daily sma | ≤0.5R | 50 / 11 | 36.7% | 54.0% | 43.0% | +11.0 pp [-2.9, +25.5] |
| daily sma | >0.5–1R | 51 / 10 | 46.5% | 49.0% | 45.1% | +3.9 pp [-9.1, +12.1] |
| daily sma | >1–2R | 92 / 11 | 43.8% | 45.7% | 45.1% | +0.5 pp [-9.7, +10.5] |
| daily sma | >2R | 941 / 21 | 44.5% | 45.4% | 43.6% | +1.8 pp [-1.3, +4.8] |
| daily sma | Unknown | 0 / 0 | — | — | — | — |
| hourly bb | ≤0.5R | 14 / 6 | 47.6% | 57.1% | 46.4% | +10.7 pp [-4.5, +50.0] |
| hourly bb | >0.5–1R | 11 / 5 | 46.7% | 36.4% | 45.5% | -9.1 pp [-50.0, +34.7] |
| hourly bb | >1–2R | 15 / 5 | 34.0% | 26.7% | 36.7% | -10.0 pp [-18.4, +16.7] |
| hourly bb | >2R | 1094 / 21 | 44.7% | 46.2% | 43.8% | +2.3 pp [-0.4, +5.1] |
| hourly bb | Unknown | 0 / 0 | — | — | — | — |
| daily bb | ≤0.5R | 0 / 0 | 62.5% | — | — | — |
| daily bb | >0.5–1R | 0 / 0 | 35.7% | — | — | — |
| daily bb | >1–2R | 0 / 0 | 47.2% | — | — | — |
| daily bb | >2R | 1134 / 21 | 44.2% | 45.9% | 43.8% | +2.2 pp [-0.5, +4.8] |
| daily bb | Unknown | 0 / 0 | — | — | — | — |
| sma confluence | ≤0.5R | 8 / 4 | 80.0% | 25.0% | 43.8% | -18.8 pp [-50.0, +25.0] |
| sma confluence | >0.5–1R | 15 / 6 | 25.0% | 53.3% | 40.0% | +13.3 pp [+3.3, +37.5] |
| sma confluence | >1–2R | 38 / 9 | 35.6% | 44.7% | 48.7% | -3.9 pp [-17.4, +20.3] |
| sma confluence | >2R | 1073 / 21 | 44.6% | 46.0% | 43.7% | +2.4 pp [-0.5, +5.3] |
| sma confluence | Unknown | 0 / 0 | — | — | — | — |

## Primary near-versus-far comparisons

Each band is compared with >2R within the same family. Excess difference subtracts each group’s matched coin result before comparing groups.

| Family | Band vs >2R | Raw target-rate difference (95% interval) | Difference in excess over coin (95% interval) |
|---|---|---|---|
| hourly sma | ≤0.5R | +0.8 pp [-8.5, +11.5] | +0.5 pp [-8.6, +10.2] |
| hourly sma | >0.5–1R | +12.2 pp [+3.6, +20.7] | +9.6 pp [-0.3, +19.0] |
| hourly sma | >1–2R | +0.9 pp [-6.0, +8.1] | -0.3 pp [-6.3, +6.3] |
| daily sma | ≤0.5R | +8.6 pp [-7.1, +27.9] | +9.2 pp [-5.2, +25.0] |
| daily sma | >0.5–1R | +3.6 pp [-11.9, +13.2] | +2.2 pp [-11.3, +10.5] |
| daily sma | >1–2R | +0.3 pp [-10.2, +11.1] | -1.2 pp [-12.0, +9.7] |
| hourly bb | ≤0.5R | +11.0 pp [-2.4, +53.3] | +8.4 pp [-7.1, +46.9] |
| hourly bb | >0.5–1R | -9.8 pp [-48.0, +31.2] | -11.4 pp [-53.4, +33.6] |
| hourly bb | >1–2R | -19.5 pp [-34.7, +14.4] | -12.3 pp [-20.7, +12.7] |
| daily bb | ≤0.5R | — | — |
| daily bb | >0.5–1R | — | — |
| daily bb | >1–2R | — | — |
| sma confluence | ≤0.5R | -21.0 pp [-46.9, +29.6] | -21.1 pp [-50.6, +23.2] |
| sma confluence | >0.5–1R | +7.3 pp [-9.0, +33.8] | +11.0 pp [+0.6, +34.0] |
| sma confluence | >1–2R | -1.3 pp [-17.2, +23.8] | -6.3 pp [-19.8, +18.9] |

## Interpretation and integrity

Intervals resample all 21 sessions, keeping overlapping origins together, with 2,000 draws and seed 20260919. Sparse groups can have no interval. All intervals are exploratory and unadjusted for multiple comparisons; isolated positive cells do not establish a reliable location filter. Raw counts and the unchanged cross-month support criterion are in coverage.json.

These are associations and historical first-touch measurements, not explanations of internal model reasoning, executable fills, or returns. Hourly/daily indicators use completed regular-session buckets and Nasdaq-only data. Scout has not been retrained or promoted.

Verification: 17 focused tests passed; all 1,134 forecast and context identities were checked; 27,144 independent target/stop checks and 150 summary rows reconciled. No missing Kronos outcome rows. Original May/June files remain unchanged.

Artifacts: frozen_config.json and protocol.md; immutable forecasts/base; prediction_contexts.jsonl; classifications.csv and coverage.json saved before outcomes; outcomes.csv; report.json; summary.csv; comparisons.csv; verification.json and independent_verification.json; manifest.json.
