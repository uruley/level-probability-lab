# Companion v0.1 diagnosis

The fixed models fit May patterns that did not carry reliably into June.
This is consistent with overfitting and/or unstable relationships under changed
conditions; these diagnostics cannot uniquely identify a cause. No refitting,
feature selection, threshold adjustment, July reads or new model promotion.

## Findings

- Trade companion Brier was 0.23637 on its May training rows versus constant
  0.24660. On June it was 0.25783 versus constant 0.24949. Training performance
  is in-sample and is not independent evidence of predictive value.
- June probability variation was poorly related to outcomes. For the trade
  model, the 73 predictions at or above 60% averaged 68.66% probability, but
  Kronos won 47.95% of those cases. The 316 predictions below 40% averaged
  34.65%, but Kronos won 50.63%. These post-hoc groups are descriptive only.
- The average predicted probability (45.51%) was fairly close to the observed
  June win rate (46.65%). The central problem was how probabilities varied by
  row, rather than a large overall mean offset. Linear descriptive calibration
  slope was 0.0525 for trade and 0.0287 for candle (not fitted recalibrators).
- Both models still lose to the constant baseline after removing any single
  June session. Trade was worse in 14/21 sessions and candle in 15/21.
- June volatility features shifted: mean ATR/close was 1.41 May standard
  deviations higher, and its standard deviation was 2.15 times May's. This
  indicates input distribution change, not proof that it caused the failure.
- Higher-timeframe inputs deserve scrutiny. In the fixed trade model, setting
  that feature family's standardized values to zero (May means) reduced June
  Brier by 0.00578, but still left it above the constant baseline. This artificial
  substitution can create unrealistic combinations; it is neither causal
  attribution nor the performance of a properly retrained reduced model.
- Setting just trade features to May means changed Brier by only -0.000364.
  This is consistent with their small incremental contribution in this model.

## Implication

Do not add complexity merely to improve this used June score. A reasonable next
separate experiment is a smaller feature set with multiple chronological
development folds and training-only model selection, plus a train-frequency
baseline in each fold. Check whether any lift survives different sessions and
sampling seeds. Candle history can broaden development, but trade coverage and
pretraining exposure limit which comparisons and claims are possible. Reserve
a genuinely unexamined final period only after the exposure audit.

## Artifacts and verification

`data/companion_model_v01/diagnosis/` contains report.json, session_diagnostics.csv,
feature_shifts.csv and coefficients.csv. Reproduce with
`scripts/diagnose_companion_v01.py`. Verified the Brier variance/covariance
identity, probability-bin counts, agreement with the original June scores,
and unchanged frozen-model hash. The original fitted artifacts are preserved.
