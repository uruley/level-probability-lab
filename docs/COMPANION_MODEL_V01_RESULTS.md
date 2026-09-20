# First companion model development results

The first logistic companions did not improve June probability forecasts over
the constant May win-frequency baseline. Adding trade features did not establish
an incremental benefit. This is development evidence, not a final holdout test.

The protocol was frozen in `docs/COMPANION_TRAINING_V01.md` before fitting.
Both arms used identical rows: 1,080 May origins for fitting and 1,134 June
origins across 21 sessions for evaluation. There were no ties or exclusions.
Base, seed 42, 25 paths, 120 candles, approximate amount remained fixed.
Target: probability that Kronos's +5 median close beats unchanged-price absolute
error. May win frequency was 44.17%; June observed frequency was 46.65%.

| System | Brier (lower better) | Log loss | Accuracy at 0.5 | Forecast-selection MAE |
|---|---:|---:|---:|---:|
| Constant May frequency | 0.249493 | 0.692145 | 53.35% | $0.631014 |
| Candle and Kronos companion | 0.257337 | 0.709421 | 52.12% | $0.636075 |
| Same plus trade features | 0.257828 | 0.710575 | 53.26% | $0.634800 |

Forecast selection uses Kronos if predicted win probability >=0.5, otherwise
unchanged. Its MAE is combined over all the same origins. Always unchanged had
MAE $0.631014; always Kronos had MAE $0.665573. Neither companion's gate beat
always unchanged in this development sample.

Paired whole-session bootstrap intervals (2,000 replicates; negative is better):

| Difference | Mean | 95% interval |
|---|---:|---:|
| Trade minus candle Brier | +0.000491 | [-0.000490, +0.001530] |
| Candle minus constant Brier | +0.007844 | [+0.003035, +0.012828] |
| Trade minus constant Brier | +0.008335 | [+0.003182, +0.013438] |
| Trade minus candle gate MAE | -$0.001275 | [-$0.003326, +$0.001042] |

Both probability models were worse than the constant baseline under this
session-bootstrap comparison. Trade-versus-candle intervals cross zero. One
development month, prior research on these periods, fixed-seed sampling and
cross-session dependence limit generalization. These results do not establish
that all indicators or all companion approaches are useless.

The NumPy logistic implementation passed two focused behavior tests. Independent
checks verified May-only scaler statistics, converged likelihood gradients,
all 1,134 saved June probabilities, Brier scores and combined gate MAEs.
The deterministic ridge penalty was 0.1; no hyperparameter sweep or June tuning.
No neural training, July evaluation, new inference or paid downloads occurred.

Artifacts in `data/companion_model_v01/`: frozen_model.json (both coefficient
sets, scalers, columns, input/protocol hashes), june_predictions.csv, report.json
(including fixed-bin reliability), and verification.json.

Do not promote either model as a validated forecast selector. Preserve this
version. Any next diagnostic or revised model should be separately versioned;
do not escalate to trees solely to seek a better June score.
