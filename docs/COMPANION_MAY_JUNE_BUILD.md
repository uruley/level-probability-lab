# Companion May and June development build

The v0.2 feature table is expanded over all saved May/June 2026 Base origins.
No model fitting, predictive scoring, new inference, downloads, or July reads
were performed by this build.

| Partition | Sessions | Forecast rows |
|---|---:|---:|
| May development fitting pool | 20 | 1,080 |
| June development selection pool | 21 | 1,134 |
| Total | 41 | 2,214 |

Each session has 54 saved origins, five minutes apart, with forecast cutoffs
from 11:30 through 15:55 New York time. This is the archived five-minute cadence,
not an every-minute dataset. Each row has 41 candidate features and five metadata
fields. Both partitions are previously used development data, not final holdouts.

All 2,214 rows have complete candle and trade inputs. There are no missing
archived forecasts, excluded sessions/origins, null feature values, or infinite
numeric values. Outcomes are in separate files keyed by the input-package ID.
The input candle source matches its frozen archive hash, and every individual
forecast's original input-window hash was verified before reuse. Trade features
match the accepted May/June audit. Model settings remain Base, 120 bars, 25 paths,
seed 42 and approximate amount.

Validation: 14 focused regression tests passed. Future-candle mutation checks
passed for one origin in each of 41 sessions. Independent rebuilding reproduced
one exported feature row per session, and all 41 corresponding label timing and
actual-close checks passed. All feature/label key sets match, and outcome columns
are absent from the feature tables. These are integrity checks, not performance
evidence or a comprehensive pretraining-data exposure audit.

Outputs: `data/companion_v02/may_june/`

- `features_may.csv` and `features_june.csv` for inspection, plus parquet copies.
- `labels_may.parquet` and `labels_june.parquet`, separate from input features.
- `input_packages/` for the frozen evidence underlying each row.
- `report.json` for session coverage, exclusions, hashes, and source provenance.
- `verification.json` for independent artifact checks.

Reproduce with `scripts/build_companion_may_june.py`, then
`scripts/verify_companion_expansion.py`. Original baseline forecasts and prior
study outputs are not changed. Additional forecast settings or Small forecasts
would be separate builds. The next step is to freeze a modest companion fitting
and selection protocol before fitting May and evaluating June development results.
