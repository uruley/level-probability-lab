# Kronos Lab goals

Updated 2026-09-19 from the user's clarified objective.

2026-09-24 follow-up supersedes RTH-only live warmup below: user requested
premarket candles and premarket ghost forecasts. Webull one-minute path now
uses PRE + RTH (04:00 Eastern through exchange close), tagged `pre-rth-v1`.
Keep this experiment separate from prior RTH evidence. No fine-tuning yet.

2026-09-24 user-requested experiment: default to 400 completed one-minute inputs
and display 50 future one-minute candles on the extended chart. Use prior
regular sessions for opening warmup; do not invent missing bars. Keep five-minute
evaluation separate. Verify this setup before TSLA fine-tuning; more context
and a longer horizon have not demonstrated better accuracy.

## Proposed next research layer: online Kronos reliability

2026-09-24: add a separate River online-learning experiment that runs beside
Kronos. River's first job is not to forecast price independently; it estimates
the probability that a specific Kronos directional forecast is correct given
only information available at the forecast origin. Score each River prediction
before updating it with the resolved outcome. Keep Kronos and River decoupled
(GPU forecaster vs lightweight CPU learner), persist the chronological event
stream, and evaluate calibration with Brier/log loss in addition to accuracy.

Start with existing candle/context fields. Time-and-sales, liquidity summaries,
drift detection, and additional forecasters are later controlled branches.
Do not fine-tune Kronos continuously and do not treat River confidence as a
trade-win probability. Full design: [RIVER_ONLINE_LEARNING.md](RIVER_ONLINE_LEARNING.md).

## Current priority: forecast reliability by market location

2026-09-23 follow-up: fixed matched June SMA200 comparison shows 12/57
rejections versus 11/57 controls; no convincing added value. See
`SMA200_MATCHED_V1_RESULTS.md`. Preserve rules; no new indicator search or
Scout training on this evidence. Prospective confirmation plan is saved for
Sep24–Oct21 but has not been collected or evaluated. July remains sealed.

2026-09-23: user requested session VWAP and the 200-period one-minute simple
moving average as candidate areas. Added separate chart overlays and fixed
June zone-response v2 study; see `ZONE_RESPONSE_V2.md`. Freeze these levels
at each origin and retain all quality/outcome categories. They are hypotheses,
not proven support/resistance or calibrated trade probabilities. Chart VWAP
is a candle approximation; study VWAP uses audited Nasdaq trade summaries.

2026-09-20: user also requested a separate one-hour visual forecast. Implemented
with 120 completed five-minute inputs and twelve forecast candles from Base;
minute-chart range overlay, ending-close marker and expandable detail chart.
Record and score this horizon separately; do not infer accuracy from prior
five-minute studies. Daily forecasts are explicitly deferred. See
`docs/KRONOS_LAB_APP.md` for the input/scoring contract.

User-approved direction, 2026-09-19. This section supersedes the earlier
"next milestone" ordering below. It is a roadmap, not a claim that these
features or a new Scout model are already implemented.

Central question: **Under what market conditions and at which price locations
are Kronos forecasts more reliable?** Keep Kronos generating five one-minute
candles. Record the context in which each forecast happened, then score its
range and frozen target/stop outcomes by that context. Candidate zones must
earn the label "high probability" through evidence, not indicator names.

### Next implementation sequence

1. Add chart overlays and a versioned, immutable context snapshot linked to
   each forecast ID. Start with previous-day high/low, current-session high/low
   so far, a small fixed set of common moving averages, and hourly/daily
   Bollinger Bands. Exact periods, session conventions and distance thresholds
   are now fixed in market-context-v1: SMA 5/10/20/50/100/200, BB20 x2,
   regular-session hours anchored at open, and 0.5R confluence proximity.
   The first context snapshots, selectable level overlays and exploratory
   grouped touch counts are implemented. The first matched-baseline batch run
   is complete: `data/location_evaluation_v1/RESULTS.md`. Five strict confluence
   origins across two sessions are insufficient for a reliable conclusion.
   Broader fixed bands were then evaluated under a separate v2 protocol:
   `data/location_evaluation_v2/RESULTS.md`. No reliable positive primary
   location advantage was established. The unchanged-category August expansion
   is now complete: `data/location_evaluation_v3_august/RESULTS.md`, 1134 origins
   across 21 sessions. Overall five-minute 1:1 was 45.9% versus 43.8% matched
   coin, with the excess interval crossing zero. Hourly SMA >0.5–1R was 57.0%
   across 86 origins, an exploratory candidate without stable prior-month
   confirmation. Strict confluence remains sparse. Preserve categories and
   seek chronological confirmation after auditing exposure; do not chase
   thresholds or promote a Scout rule from the best August cell.
2. Record distances from reference price to levels (price and volatility-scaled),
   average slopes, band position/width, data availability and indicator timestamps,
   together with existing Kronos direction, sampled paths and range summaries.
   Keep realized outcomes separate from prediction-time inputs.
3. Build a visual "results by location" view: target first, stop first,
   neither/expired, ambiguous, missing and open counts, sample sizes and time
   to resolution. Preserve separate five-minute scoring and extended tracking
   (up to 60 elapsed minutes or session close) for 1:1, 2:1 and 3:1 setups.
4. Only after auditing those records, design a separate Scout experiment that
   combines Kronos outputs with market context to estimate target-before-stop
   outcomes. Preserve the existing close-based Scout as a historical baseline.
   The new target, horizon, model method and evaluation protocol are not yet chosen.
5. Later investigate time-and-sales as an additional context branch: available
   trade activity near the recorded levels may help distinguish otherwise similar
   setups. Compare against the same model without trade features. Raw tape does
   not become a new Kronos input merely because Scout or the chart uses it.
   Fibonacci is a deferred candidate, not part of the first feature set.

### Data flow and interpretation

Completed candles -> Kronos -> five forecast candles and sampled paths.
Past market history -> context snapshot and chart overlays.
Kronos outputs + context -> location-based evaluation -> future Scout experiment.
Later: synchronized, already-available trade summaries -> context/Scout branch.
Revealed future observations -> separate outcome ledger, never input features.

Use only information available at prediction time. Previous-day levels use a
completed session; today's levels mean "so far." Hourly and daily indicators
initially use completed bars only, with enough prior history and explicit session
anchoring. Never substitute the eventual daily high/low or an unfinished higher-
timeframe candle. Keep unknown/missing values explicit. Nasdaq data is venue-only.

Compare with simple direction baselines under identical origins, levels and
deadlines. Roughly 50% target-first alone is not evidence of an advantage.
Disclose percentage denominators and overlapping forecasts; use chronological
development and session-level uncertainty rather than treating each minute as
independent. Indicator grouping is exploratory and subject to selection bias.
July remains sealed; August is development. Reserve any future test only after
checking prior exposure. Context associations do not explain Kronos's internal
reasoning or establish causation.

### Current Scout status

Scout is offline research, not connected to the replay display. The existing
model uses regularized logistic regression to estimate whether Kronos's +5 close
beats the unchanged-price baseline. The latest small-feature experiment used
seven Kronos-output features; it did not establish a reliable forecasting gain.
Changing to range or first-touch outcomes requires new labels and retraining,
not relabeling its existing probabilities. Current replay touch scores are Kronos-
derived setup measurements, not Scout predictions.

## Product objective

The companion model is named **Scout**. Use this name in future documentation
and interface labels. Its current research target is whether Kronos's five-minute
median close forecast beats the unchanged-price baseline. The name does not
imply demonstrated predictive value; existing experiment versions are preserved.

A visual historical QQQ replay machine feeds completed market observations
into Kronos Base, projects the next five one-minute candles, and then reveals
and scores actual outcomes. Agents can run reproducible experiments using the
same input and scoring rules. Small remains a comparison option.

The user also wants to understand what the forecast responds to: what the model
was shown, which observed patterns accompany a forecast, and how sensitive the
forecast is to those inputs. Explanations must distinguish evidence from inference.

## Current inputs and limits

- Each forecast uses 60, 120 (default), or 240 completed same-session QQQ bars.
- Numeric fields: open, high, low, close, Nasdaq volume, and approximate amount
  calculated as volume times close. Timestamp features accompany the bars.
- The existing adapter normalizes numeric fields within the input window.
- Base runs locally on the GPU. Historical replay does not update its weights.
- Extra raw-trade columns cannot simply be appended to the current model input.
  Raw trade integration is an input/interface question as well as a compute
  question; Base working with candles does not establish raw-tape compatibility.
- No LLM interpretation layer or trade tape is currently connected to the app.
- Actual summed trade-dollar amount is now an optional May/June input mode;
  the original approximation remains the default comparison. See the app guide
  for the development integration check and its limits.

## Later milestone: synchronized time-and-sales replay

Use the already acquired May–July 2026 Nasdaq QQQ trades. Begin implementation
and inspection on May/June development sessions. Display trade price, size,
timestamps, and recorded side with unknown side explicitly preserved. Synchronize
the tape with the replay clock; do not expose future trades to forecast or
interpretation requests. Label the feed as Nasdaq-only.

Separate raw tape and derived trade summaries from the actual Kronos input.
Show which fields each component receives. A future trade-aware predictor or
correction must be a separately identified experiment, with frozen settings and
matched candle-only controls. Do not claim that displaying trades makes Kronos
trade-aware. Replacing approximate amount with actual summed price times size
is now implemented as a controlled input option, not an established improvement.

## Explanation objective

1. Input evidence: show the exact trailing candles, volume, time information,
   and any separately supplied trade summaries available at forecast time.
2. Descriptive interpretation: summarize observable movement, ranges, and
   activity. Any LLM narrative is an interpretation of supplied evidence, not
   a recovered internal reasoning trace from Kronos.
3. Sensitivity experiments: compare forecasts under predeclared, coherent
   changes to inputs while holding model and sampling settings fixed. Report
   output changes and limitations; artificial inputs may be out of distribution
   and do not establish causal reasons for the original forecast. Synthetic
   probes must be clearly separate from observed market data and scored runs.
4. Predictive claims: save structured judgments and evidence before revealing
   outcomes, then evaluate whether they add value against a matched baseline.

The current adapter exposes sampled forecast paths, not a verbal reasoning
trace. Neither plausible prose nor an attention visualization alone would prove
why a specific candle was predicted.

## Completed experiment and evaluation rules

Time-and-sales acquisition and quality checks are complete. The first separate
trade-feature correction study used May for fitting, June for selection, and
July for its frozen final evaluation. Across 1,188 matched July origins, the
trade correction worsened five-minute MAE by 0.94% versus candle correction.
See `data/trade_comparison_v1/RESULTS.md`.

Preserve this result. July must not be used to retune that study or be relabeled
as untouched for a new experiment. August is already development. Audit all
prior data exposure before reserving another test period. Interactive replay
scores are exploratory, not a sealed evaluation.

Keep original forecasts immutable, retain raw sampled paths, disclose display
repairs, compare with unchanged-price forecasts, and keep missing outcomes
unscored. Sample spread is not a calibrated confidence guarantee.

No new data purchase, neural training, paid LLM service, or live subscription
is authorized by this goals update. Existing acquisition and secret-handling
safeguards remain in force. The older boundary-probability study remains separate.

September20 update: the user subsequently authorized data-only connection to
the existing official Webull feed. Completed QQQ candles now support live
Kronos forecasts and local recording/replay. No account/order access or new
subscription purchase is included. See [Webull live setup](WEBULL_LIVE.md).
Observe a market-hours run before declaring live delivery verified; preserve
source labels and keep exploratory live scores separate from sealed studies.


## September 22: stacked forecast charts

The Lab now displays the main one-minute chart, an expanded five-minute chart,
and a separate hourly chart above the score tables. The existing five-minute
model input remains 120 completed five-minute candles, producing twelve bars
(next hour). The new hourly branch uses 60 completed full regular-session
hourly candles and produces five hourly candles with Kronos Base.

Hourly bars start at 09:30 Eastern. Forecasts now use the last completed
full hour, including requests between boundaries. Before the first hour closes,
the previous session supplies the latest full hour. Input cutoff and request
time are recorded separately; later candles are excluded from model input. The short closing half-hour is excluded, as are closed
market periods. Future targets can continue into the next trading session.
Missing input slots block prediction; no candles are invented. Automatic hourly
updates are enabled by default, with frozen forecast selection and per-bar close
errors as actual hours complete. Replay steps preserve hourly boundaries.

Raw sampled paths, input provenance and frozen display candles are saved in
hourly_bar_forecasts.jsonl; revealed outcome snapshots in hourly_bar_outcomes.
This is an exploratory multi-timeframe display, not a validated swing-trade
model or an agreement-based signal. July sealed studies are unchanged.

Validation: 145 Python tests passed, chart/playback browser logic tests passed,
and real local Base inference produced twelve five-minute and five hourly bars
on an August development replay.


September 23 update: the middle five-minute chart is replaced by a fifteen-minute
forecast using completed one-minute inputs and 15 future one-minute bars.
The selected input lookback applies. New records use fifteen_minute_forecasts.jsonl
and fifteen-v1 IDs; legacy five-minute/hour records are preserved. The middle
chart retains a separate frozen predicted-close line for every issued forecast
alongside actual closes, after elapsed ghost candles disappear. These lines are
displayed for the current replay session; full paths remain saved on disk.
The true hourly chart remains five hourly bars.
