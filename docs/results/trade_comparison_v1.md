# QQQ three-month research results

This test did not establish incremental predictive value from time-and-sales.

May 2026 was used for fitting, June for selecting regularization, and July for one frozen final test.

The final comparison contains **1,188 matched origins across 22 July sessions**.

## Primary result: five-minute close error

Trade correction versus the same correction using candles only: **-0.94% relative MAE improvement** (positive is better).
Paired mean error difference: **$+0.00463**, with session-bootstrap 95% interval **[$+0.00052, $+0.00978]**. Negative differences favor trades.

The predeclared requirement was at least 1% improvement and an interval entirely below zero.

| Engine | July +5 minute MAE | July +5 minute RMSE |
|---|---:|---:|
| Kronos Base | $0.52532 | $0.70143 |
| Kronos Small | $0.51273 | $0.68645 |
| Unchanged price | $0.48808 | $0.65143 |
| Base + candle correction | $0.49291 | $0.65972 |
| Base + candle and trade correction | $0.49754 | $0.66835 |

## Every forecast horizon

| Horizon | Candle-control MAE | Trade-augmented MAE | Relative improvement | Paired 95% difference interval |
|---|---:|---:|---:|---|
| +1 minute | $0.25883 | $0.25909 | -0.10% | [-0.00161, +0.00215] |
| +2 minute | $0.34173 | $0.34700 | -1.54% | [+0.00043, +0.01142] |
| +3 minute | $0.40177 | $0.40689 | -1.27% | [+0.00082, +0.01039] |
| +4 minute | $0.43866 | $0.44522 | -1.50% | [+0.00195, +0.01201] |
| +5 minute | $0.49291 | $0.49754 | -0.94% | [+0.00052, +0.00978] |

## June baseline, before the final test

| Engine | +5 minute MAE | Flat-price MAE | Up-event Brier | May-climatology Brier | Sampled close interval coverage |
|---|---:|---:|---:|---:|---:|
| Kronos Base | $0.66557 | $0.63101 | 0.28518 | 0.25072 | 54.1% |
| Kronos Small | $0.64575 | $0.63101 | 0.27236 | 0.25072 | 57.7% |

## Data, method, and limits

- Databento acquisition completed once under a $3 cap. Fresh quoted estimate: **$2.484871**. Actual invoice is not exposed by the adapter.
- May/June quality check: 15,990 reconstructed minute bars; 0 OHLCV field mismatches. Unknown-side volume: 16.37%.
- July quality check: 8,580 minute bars; 0 OHLCV field mismatches. Excluded test origins/sessions: 0.
- Ridge penalties selected on June: candle control 10; trade augmentation 100. Scalers and coefficients were fitted on May only.
- Frozen Base and Small use 120 completed candles, 25 sampled paths, five elapsed-minute targets, and seed 42. Predictions and actual outcomes are saved in CSV.
- All arms use identical eligible origins. The trade comparison uses the same Base forecast and correction family; it isolates incremental trade features.
- Confidence intervals resample whole sessions (2,000 replicates); a single month and cross-session dependence limit generalization.
- Direction metrics, where reported in JSON, exclude predicted and actual neutral moves. Unchanged price makes no directional call.
- Nasdaq venue prints are not the consolidated tape. This is forecast research, not a profitability or execution claim.
- No neural weights were trained and no LLM explanation layer was scored. July results must not be used for retuning this study.

## Artifacts

- `holdout_predictions.csv`: all five arms, actual and predicted closes, all horizons.
- `development_validation_predictions.csv`: matched fitting/selection-period outputs.
- `holdout_report.json`: all metrics, paired intervals, exclusions, and frozen model hash.
- `frozen_model.json`: coefficients, scalers, selected penalties, ordered features, and input hashes.
- `../kronos_baseline_v1/`: immutable raw model paths, baseline scores, provenance and reports.
- `../trades_study/`: trade feature files, reconciliation reports and quality gates.
