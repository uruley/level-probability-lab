# Smaller companion chronological development protocol

Post-hoc follow-up to v0.1. June findings motivated this study, so June is used
development data, not an independent validation of the revised design.
Freeze these three candidates before fitting:

1. forecast: five k_d*_atr changes, k_path_iqr5_atr and k_path_frac_up5 (7).
2. compact: forecast plus tod_frac_session, ret_1m, ret_5m_sum,
   atr14_over_close, rvol_20, nasdaq_vol_ratio_20, bb_pctb (14).
3. compact_trades: compact plus the seven existing ts features (21).

Exclude higher-timeframe, previous-session, weekday and moving-average features.
This exclusion is a hypothesis based on used development data, not proof that
those families lack value. No tuning of penalty, sampling, thresholds or columns.

Use the existing v0.2 eligible, complete, non-tie origin rows and frozen Base
forecasts. May has 20 sessions. Fold 1 fits sessions 1–10 and checks 11–15;
fold 2 fits 1–15 and checks 16–20. Each fold fits its own standardization,
constant-column removal and ridge logistic parameters, penalty 0.1. Baseline
is that fold's training win frequency. All training labels must be available
before the next evaluation origin.

Rank candidates by pooled Brier over the ten out-of-fold May sessions, ties
broken by fewer columns. Include train-frequency baseline as a candidate:
if no model beats it, select baseline. Save selection before June prediction.
Fit the selected model on all May only; evaluate once on June development rows.
Report Brier, log loss, accuracy and paired session-bootstrap Brier differences
(2,000 replicates, seed 20260919). Also report fixed-threshold 0.5 gate MAE
on June. No June-driven reselection, retraining or threshold adjustment.

Preserve v0.1. Save fold predictions, fitted models, selected model, hashes,
exclusions and final June development predictions. No July access, no new
market data, and no new final-test claim. Seed sensitivity remains a separate
future experiment; this run holds archived seed 42 fixed.
