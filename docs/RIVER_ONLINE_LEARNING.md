# River online-learning layer

Status: **proposed experiment — not implemented**

Date added: 2026-09-24

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

As of 2026-09-24 this document records the design decision only. No River
dependency, online estimator, River feature contract, River dashboard, or live
learning loop has been implemented yet.
