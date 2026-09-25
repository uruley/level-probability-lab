# River online-learning layer

Status: **v1 implemented and offline-tested; live worker opt-in and currently off**

Date added: 2026-09-24

## Implemented v1 contract (supersedes proposal wording below)

`src/level_probability_lab/river_online.py` contains the independent CPU learner,
event journal, replay CLI, Webull-recording consumer and read-only status adapter.
Kronos generation, IDs, input windows, sampled paths and forecasts are unchanged.
The existing `lab.py` only adds authenticated POST `/api/river`; `lab_web/app.js`
adds the read-only panel. River does not import torch, call a feed or submit orders.

### Model and grouping

Optional dependency `river==0.22.0`, installed with `pip install -e ".[river]"`.
Native `preprocessing.StandardScaler(with_std=True)` followed by
`linear_model.LogisticRegression(optimizer=optim.SGD(0.01), l2=0.001)`;
other estimator defaults are pinned by River version. Explicit calls keep scaler
updates out of prediction: predict uses existing scaler state, then the scaler
and classifier learn only on eligible resolved labels. Feature keys are sorted
before computation for exact restart ordering. Model version `river-logistic-v1`.
See [River logistic regression](https://riverml.xyz/0.22.0/api/linear-model/LogisticRegression/).

Separate models are keyed by symbol, session policy, Kronos name/revision and
horizon (1,2,3,4,5). Symbol/policy/horizon are routing metadata, not numeric
categories. Lookback/path-count settings share a learner within that key;
the original immutable forecast ID identifies those settings. No 50-minute,
hourly, Scout, tape, Level 2 or neural-model integration.

### Exact features: river-features-v1

Every packet is built exclusively from `input_window`, raw `sampled_paths`,
`last_input_timestamp`, `target_timestamps`, model metadata and saved
`forward_context`. No outcome dictionary or post-origin context is read.
The last six input bars must cover six consecutive elapsed minutes; all input
timestamps must be unique, ordered, and finish at the declared origin.

| Numeric feature | Definition |
|---|---|
| current_open/high/low/close/volume | Last frozen completed input bar |
| return_1 | Last close / previous close minus 1 |
| return_5 | Last close / close five elapsed minutes earlier minus 1 |
| volatility_5 | Population standard deviation of those five simple returns |
| range_5 | Mean H-L of last five bars / reference close |
| minutes_since_open | Origin clock minus 09:30 NY (RTH) or 04:00 (pre-rth-v1) |
| relative_volume_5 | Last volume / mean of last five volumes (includes last bar) |
| relative_volume_missing | 1 when denominator is zero; ratio uses 0 placeholder |
| session_vwap_approx_distance, sma200_distance | Reference / frozen context value minus 1 |
| session_vwap_approx_missing, sma200_missing | 1 when absent/invalid; distance uses 0 placeholder |
| predicted_move | Median sampled close at this horizon / reference minus 1 |
| predicted_magnitude | Absolute predicted_move |
| predicted_direction | Sign of median sampled close minus reference: -1/0/+1 |
| predicted_range | Median per-path max(high)-min(low) through this horizon / reference |
| predicted_range_missing | 1 when no valid raw OHLC path through this horizon; range uses 0 |

There are 21 numeric fields. Missing historical context is never reconstructed.
Stored context `as_of` must be no later than the input cutoff. Invalid raw OHLC
paths are excluded from range only; close median follows existing Kronos scoring.
Display repairs never enter River.

### Labels and quality

Reference = last frozen input close. Predicted direction is the sign of the
all-path median close minus reference for the matching horizon. Label 1 means
actual target close has the same nonzero direction; label 0 means the opposite.
Exact equal closes are `neutral_actual` or `neutral_forecast`, with null label.
No tolerance/threshold was fitted. This is a new binary correctness target;
it does not alter the older upper_first/lower_first/neither contract.

Target timestamps must be exactly the next five one-minute bar starts.
Horizon h becomes eligible at origin+h minutes (target bar end). All h elapsed
bars must be present, completed, unique and valid OHLC. Gaps, duplicates,
nonfinite prices and malformed duration remain incomplete. Missing futures never
train, even if a later provider correction fills them. Neutral records never train.
Directional close labels do not infer any intrabar first-touch ordering.

### Persistence and crash recovery

Each run owns `events/000000000001.json`, etc. These are separate immutable
prediction and outcome events, atomically published after flush/fsync. This uses
the repo's JSON snapshot convention instead of a new database. A single-writer
OS lock releases on process exit/crash. A partial `.tmp` is not a committed event.

Prediction events retain full features, forecast ID, symbol, origin, horizon,
target/deadline, reference and predicted close/direction, model/schema/revision,
session policy, issue and River prediction times, probability, prior sample count,
and both baseline probabilities. Outcome events retain actual close/move/direction,
quality, label, absolute/relative forecast error, saved probability, Brier/log loss,
baseline losses, resolution time and durable update intent (`updated`). A committed
update intent is reapplied on recovery if the process stopped before learning.

The event journal itself is the deterministic checkpoint. Startup creates empty
River estimators and applies each committed labeled outcome exactly once in
sequence, never recomputing saved probabilities. No unsafe pickle or second model
file can become inconsistent with a learned-event cursor. `seq` is the last
applied event; replaying it reconstructs model/scaler/baseline state. A failure
after commit poisons that process's engine; restart recovers it. Truncated,
nonchronological or incompatible journals fail visibly. Preserve the pinned
dependency/runtime for bitwise reproducibility; startup work grows with history.

### Replay

```powershell
.venv/Scripts/python.exe -m level_probability_lab.river_online replay --start 2026-09-15 --end 2026-09-24 --output data/river_replay_new_run
```

Requires a fresh output directory and explicit inclusive date bounds. CLI reads
existing official Webull five-minute forecast records and per-symbol daily
recordings only; it rejects ranges overlapping July 2026. The reusable `replay`
function accepts an explicit saved-forecast list and a bar loader. No random
shuffle, fresh Kronos inference or data purchase occurs.

Replay is explicitly **counterfactual origin-time simulation**: original issue
time is preserved, but predictions are simulated at input cutoff, with labels
released at each target bar end. At equal time, all eligible outcomes score/learn
before new predictions; stable packet IDs break ties. A later forecast cannot
teach an earlier one. Latest recorded candles may include provider corrections;
this is not a reproduction of first-arrival feed latency or historical live River.
Original forecast and outcome stores are not rewritten. Rejected forecasts and
quality counts are reported separately. Live and replay never share learned state.

### Live worker and dashboard

```powershell
.venv/Scripts/python.exe -m level_probability_lab.river_online live --replay-report data/river_replay_v1_verified/report.json
```

Starting is opt-in; a matching replay report with scored observations is a technical
gate, not a performance/promotion gate. It starts a fresh live learner, records its
start time under `data/kronos_lab/river_live/run.json`, and consumes only forecasts
issued since that start. Restarts keep that boundary and recover pending outcomes.
The independent worker tails the existing append-only `forecasts.jsonl` and reads
the recorder's daily Webull snapshots every two seconds. No browser/API request
starts it, no queue is shared with GPU inference, and a worker failure cannot
propagate into Kronos. The existing browser/recorder still must supply candles.

Live River prediction time is worker observation time. If it is at or after the
first target bar end, or issue time is unknown/invalid, the record is excluded as
late/unknown. Thus even +5 is excluded if the worker already missed +1. Predictions
partway through the first minute are allowed, with their exact issue time saved;
this is not an execution-latency study. Previously pending outcomes resolve before
new predictions each cycle. Out-of-order clocks are rejected. Forecasts appended
after a cycle's captured clock are deferred, not lost. Partial JSONL tails wait.

Missing outcomes receive 90 seconds of recorder grace, then become permanently
incomplete. Available bars freeze at the first resolving poll; later corrections
never relabel/retrain. Outcome event time is actual worker resolution time, so
delayed labels never retroactively change earlier saved probabilities. Status
exposes pending count, oldest due time, late predictions, rejected packets, quality
counts and last event; `timing.json` records cycle duration. No queue drops are
performed. Full status/report rebuilding and startup recovery are linear in history;
long-duration throughput/compaction remain unbenchmarked.

POST `/api/river` reads `river_live/status.json` only, retains the Lab local-host
and token checks, and works without importing River. A stopped worker becomes
stale after 30 seconds. UI shows selected forecast +1..+5 direction/probability,
observations, Brier, recent Kronos accuracy and descriptive calibration status.
The status snapshot includes the most recent 500 horizon packets; older records
remain in the journal. Historical replay metrics are in the separate run report.

### Metrics and validation

Per model key: prediction count, scored count, correctness-classifier accuracy
(probability >=0.5), raw Kronos directional accuracy, Brier, natural-log loss,
mean confidence on scored observations, last-100 resolved Kronos accuracy and ten
equal-width probability buckets with counts, mean probability and observed rate.
Buckets below 20 are marked sparse; fewer than 100 group observations are labeled
insufficient. Larger counts still mean descriptive calibration, never validation.

Baselines are pre-update expanding historical correctness and last-100 resolved
correctness, separately per model key; both cold-start at 0.5. Probabilities are
frozen at prediction, not recalculated at outcome time. These unsmoothed baselines
can output 0/1 early, heavily penalized by log loss (clipped at 1e-15 only for logs).
No model/threshold search was performed. Constant 0.5 gives Brier 0.25 and log loss
0.693147 on every eligible binary outcome and is an additional sanity comparison.

September 15–24 recording replay: 1,539 accepted forecasts / 7,695 horizon packets,
6,340 complete/scored, 1,331 incomplete and 24 neutral actuals; 11 input forecasts
rejected. There are 40 model groups. Initial pooled River Brier **0.258909**, log
loss **0.719092**, correctness-classifier accuracy **50.84%**, Kronos correctness
**50.33%**. Expanding baseline Brier 0.259160/log loss 0.991615; rolling baseline
0.260590/0.994568. River does **not** beat constant 0.5. No reliable benefit or
calibration claim follows. Overlapping observations and explored recordings are
not independent or untouched test evidence. Preserve all settings and results.

Artifacts: `data/river_replay_v1/` (initial check),
`data/river_replay_v1_verified/` (canonical feature-order verification).
All 11 rejected forecasts lacked a contiguous six-minute recent input window;
they were not shortened or repaired. The canonical run has the same pooled scores.
Tests cover all twelve handoff requirements plus same-time chronology, delayed
recording, writer locking, partial/concurrent append, clock reversal, duplicate
IDs, immutable exclusions and exact state reconstruction. The full offline suite
passed **228 tests**, including **19 River tests**, with dependency deprecation
warnings. All four existing JavaScript test files and app syntax checks passed;
browser inspection verified the panel's
disabled state. A market-hours live collection run has **not** been verified.

Recovery reconstructed all 15,390 canonical events and exactly matched its saved
report, taking 46.34 seconds on this machine. See `verification.json` beside the
report. Initial versus canonical event bytes differ because canonical numeric
feature ordering was added between runs; aggregate scores agree at reported
precision. Same-code shuffled-input replay tests are byte-identical. No model
checkpoint compaction or long-running production throughput claim is made.

Changed files: `pyproject.toml`, `src/level_probability_lab/river_online.py`,
`src/level_probability_lab/lab.py`, `src/level_probability_lab/lab_web/app.js`,
`tests/test_river_online.py`, `PROJECT_STATE.md`, `docs/KRONOS_LAB_GOALS.md`,
and this guide. The optional dependency installation selected pandas 2.3.3
(River 0.22 requires pandas <3); the existing NumPy/pandas combination emits
timedelta deprecation warnings. Tests pass, but a future dependency upgrade should
be independently verified and use a new experiment/runtime identity.

The remaining text records the original roadmap; later features remain proposed.

## Objective

Add a lightweight online-learning layer beside Kronos so the lab can learn,
incrementally, **when a Kronos forecast is more or less trustworthy**.

Kronos remains the market forecaster. River does not replace Kronos and does
not modify Kronos weights after every candle. River receives prediction-time
features, emits a reliability/probability estimate, then updates when the
corresponding future outcome becomes available.

Primary research question:

> Given the current market context and Kronos output, what is the probability
> that the Kronos directional forecast for this horizon is correct?

This is an experiment, not a claim of trading edge.

## Proposed live loop

```text
live completed market data
        |
        +---------------------> Kronos (GPU)
        |                         |
        |                         +--> +1m ... +5m forecasts
        |                                   |
        +--> feature engine ----------------+
                                            |
                                            v
                                      River (CPU)
                                            |
                                   reliability estimate
                                            |
                              wait for actual horizon
                                            |
                                            v
                                      outcome label
                                            |
                                            v
                                      River learns
```

Kronos and River should run as independent processes or workers. A queue or
durable store should sit between them so a failure or delay in one component
does not block the other.

## First experiment scope

Start small. Do not begin with raw tick/order-book firehoses.

For each Kronos forecast origin and each horizon, persist an immutable
prediction-time feature record containing at least:

- forecast ID, symbol, origin timestamp, horizon, session policy
- Kronos predicted direction and predicted close/move
- Kronos forecast path/range summary where already available
- current OHLCV context
- approximate/session VWAP distance
- relative/recent volume features
- short-horizon realized volatility / range context
- time-of-day/session progress
- model/version identifiers and input-policy identifiers

When the horizon resolves, attach a separate outcome record:

- actual future close/move
- actual direction relative to the frozen reference close
- directional correctness
- absolute/relative forecast error
- quality state: complete, incomplete, missing, or otherwise excluded

River must never receive future/outcome fields before prediction.

## Initial River target

The first target should be deliberately simple:

```text
P(Kronos direction is correct | Kronos output + market context)
```

Run separate horizon targets or include horizon as an explicit feature. Do not
quietly mix +1m and +5m labels as though they are the same task.

Useful outputs for the dashboard:

- raw Kronos direction
- River reliability probability
- recent prequential accuracy / Brier score
- current-regime or rolling performance
- sample count behind any displayed subgroup
- drift/change warning if a predeclared detector is used

## Learning protocol

Use prequential evaluation:

1. Receive prediction-time features.
2. River predicts before seeing the outcome.
3. Save that prediction.
4. Wait until the requested horizon resolves.
5. Score River and Kronos against the frozen outcome.
6. Update the online learner only after scoring.
7. Continue with the updated model.

This ordering is mandatory to prevent look-ahead leakage.

The online model may learn one resolved example at a time, but all results
must remain reproducible from the stored event stream. Persist model/version
metadata and enough information to replay the learning sequence in timestamp
order.

## Resource plan

Kronos Base remains GPU-oriented. River models are expected to be lightweight
enough for CPU execution. Keep inference/update timing measured rather than
assuming concurrency is free.

Do not allow River work to delay the market-data clock or Kronos forecast
generation. Backpressure, queue depth, dropped/late labels, and restart recovery
must be observable.

## Feature expansion after the first baseline

Only add a feature family after the basic reliability experiment is working and
scored against a simple baseline.

Candidate later feature branches:

- richer candle-shape and momentum descriptors
- previous-day/current-session levels already recorded by the lab
- time-and-sales summaries
- trade-size / trades-per-second / signed-flow summaries where quality permits
- spread and order-book/liquidity features if a valid feed is available
- cross-asset context
- regime features
- additional independent forecaster outputs

High-frequency feeds should normally be converted into timestamp-safe summary
features before River sees them.

## Future multi-model extension

If the lab later runs additional forecasters beside Kronos, River can be tested
as a routing/weighting layer rather than only a Kronos reliability model.

```text
current context
   |
   +--> Kronos forecast
   +--> forecaster B
   +--> forecaster C
   |
   v
online meta-model
   |
   +--> calibrated weights / reliability estimates
```

Any additional forecaster must first be evaluated independently on the same
origins and horizons. Do not assume that model disagreement or model count
improves accuracy.

## Baselines and success criteria

At minimum compare River against:

- unconditional historical Kronos correctness for the same horizon
- a rolling recent Kronos correctness rate
- a simple fixed/regularized offline classifier where appropriate
- probability calibration metrics, especially Brier score and log loss

Accuracy alone is insufficient. A model that emits useful confidence should be
judged for calibration and stability as well as discrimination.

River earns promotion only if forward/prequential evaluation shows repeatable
improvement over the declared baselines without leakage.

## Non-goals for v1

- do not fine-tune Kronos after every candle
- do not let River alter historical Kronos forecasts
- do not use outcomes as prediction-time features
- do not call confidence a trading probability without a separate trading label
- do not connect the experiment to live order execution
- do not infer institutional activity solely from a volume spike
- do not add every available feature before measuring the small baseline

## Implementation sequence

1. Define and version the River feature/outcome contracts.
2. Add durable forecast-feature and resolved-outcome records.
3. Implement chronological replay of those records.
4. Add one simple River classifier and online metrics.
5. Verify predict -> score -> learn ordering with leakage tests.
6. Run historical chronological replay before enabling live updates.
7. Add a read-only live dashboard panel.
8. Only then test extra market-context or tape/liquidity feature families.
9. Later compare multi-model routing if additional forecasters are added.

## Relationship to Scout

Scout is an existing offline companion-model research track. River is a separate
online-learning experiment.

Do not silently replace Scout or relabel old Scout results as River results.
If the projects eventually converge, define a new versioned experiment and
evaluate it against both historical baselines.

## Current state

The implementation and verified scope are recorded at the top of this document.
Later feature families, drift detection and multi-model routing remain proposed.
