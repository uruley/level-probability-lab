# Smaller companion chronological development results

The seven-feature forecast-only companion ranked best on pooled May folds and
slightly improved June Brier versus constant training win frequency. The paired
interval includes zero, and its price-forecast gate still lost to unchanged.
This is an exploratory development result, not demonstrated predictive value.

The protocol was written before this run in COMPANION_SMALL_V02_PROTOCOL.md.
May folds fit sessions 1–10/check 11–15, then fit 1–15/check 16–20: 540 combined
out-of-fold origins across ten sessions. All three models used May-fitted fold
scalers and fixed ridge penalty 0.1. No exclusions. The constant baseline was
eligible for selection; lowest pooled May Brier selected the forecast-only model.

| Candidate | Inputs | Pooled May out-of-fold Brier |
|---|---:|---:|
| Constant fold training win frequency | 0 | 0.245303 |
| Kronos forecast only | 7 | 0.242993 |
| Compact candle plus forecast | 14 | 0.247709 |
| Compact plus trades | 21 | 0.249805 |

The seven inputs are the five ATR-normalized predicted close changes, +5 sampled
close IQR/ATR, and sampled fraction above the current close. These remain derived
from Kronos, not an explanation of its internal reasoning.

The selected model was refitted on all 1,080 May rows, saved, then evaluated on
1,134 June rows across 21 sessions. June was already used in earlier development
and motivated this redesign, so it is not an independent test of the hypothesis.

| June measurement | Selected model | Constant baseline |
|---|---:|---:|
| Brier | 0.248374 | 0.249493 |
| Log loss | 0.689824 | 0.692145 |
| Accuracy at 0.5 | 52.29% | 53.35% |
| Forecast-selection MAE | $0.634774 | $0.631014 |

May selected-minus-baseline Brier: -0.002311, session-bootstrap 95% interval
[-0.005595, +0.000943]. June: -0.001120, interval [-0.004146, +0.002139]. Both
include zero. Intervals do not account for candidate-selection optimism or all
prior development choices. No robust improvement has been established.

Artifacts under `data/companion_small_v02/`: frozen_selection.json, May out-of-fold
predictions, June predictions, report.json and verification.json. All 540 May
and 1,134 June probabilities were independently reproduced; chronology,
fold-local scaling, convergence and reported June Brier were checked.
Original v0.1 files remain unchanged; no July, new downloads or new Kronos inference.

Keep the compact forecast-only model as a research candidate, not a promoted
selector. Broader chronological development and a data/pretraining exposure audit
are needed before reserving a truly independent test. Do not keep optimizing on
June or claim that the small Brier change proves improved price forecasting.
