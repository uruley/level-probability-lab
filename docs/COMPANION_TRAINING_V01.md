# Companion logistic comparison v0.1

Frozen before fitting or June scoring in this run. Research/development only.

- Inputs: v0.2 May/June Base tables; May fits, June evaluates. July excluded.
- Identical complete, non-tie, eligible origins for both arms. Report exclusions.
- Candle arm: all 34 declared non-trade inputs. Trade arm: same plus seven ts inputs.
- Weekday encoded as four indicators (Monday reference), not a linear number.
- Remove constant columns using May only; standardize using May population mean/std.
- Logistic regression minimizes mean binary cross entropy plus 0.1/2 times
  squared coefficient norm, excluding intercept. No class weighting, hyperparameter
  sweep, feature selection, calibration fitting or June retuning.
- Deterministic Newton updates with backtracking; require converged gradient.
- Baseline probability: May non-tie win frequency, constant for every June origin.
- Primary: Brier score. Secondary: log loss, reliability in five fixed probability
  bins, accuracy at fixed threshold 0.5. Probability target is conditional on non-tie.
- Descriptive forecast gate: use Kronos median +5 close if probability >=0.5,
  else use unchanged close. Report combined MAE on identical non-tie rows, plus
  always-Kronos and always-unchanged MAE. Classification wins need not improve MAE.
- Paired differences: trade minus candle and each arm minus climatology Brier;
  also trade minus candle gate error. Resample whole June sessions with replacement,
  2,000 replicates, seed 20260919. Negative favors the first-listed arm. Session
  dependence and one development month limit interpretation.
- Enforce all May label availability before June first origin. Keep outcome
  columns out of the matrix. Archive hashes, scalers, coefficients, row counts,
  per-origin probabilities/errors, and metrics. Do not change frozen prior studies.

Implementation uses NumPy logistic regression because this project environment
does not have scikit-learn or SciPy. Validate its convergence and basic recovery
behavior with offline tests before using its results. No neural model is trained.
