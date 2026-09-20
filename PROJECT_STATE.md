# PROJECT_STATE.md

## Goal

Current priority (2026-09-19): measure **where Kronos forecasts work best**.
Implemented: chart overlays and frozen prediction-time context (previous-day levels,
today's high/low so far, common moving averages, hourly/daily Bollinger Bands),
plus an exploratory results-by-location view. The first matched-baseline batch evaluation is complete but strict confluence was too sparse (5 origins/2 sessions). Fixed broader distance bands have also been evaluated in v2 without a reliable positive primary result. Next evidence should come from additional predeclared sessions using unchanged categories before considering a new target-before-stop Scout
using Kronos outputs plus context, with time-and-sales as a future additional
branch. Fibonacci is deferred. Context v1 is implemented; new Scout training remains planned. Read `docs/KRONOS_LAB_GOALS.md` for the authoritative roadmap and rules.

The companion model's user-facing name is **Scout** (not Kronos Scout).
Scout assesses the five-minute Kronos forecast versus the unchanged-price
baseline. Existing versioned experiment identifiers remain unchanged.

Active goal (updated 2026-09-19): Kronos Lab — historical replay, completed
QQQ inputs, Kronos Base forecasts of five one-minute candles, time-and-sales
integration, evidence-based interpretation, and measured actual-vs-predicted
results. See `docs/KRONOS_LAB_GOALS.md`.

Base and Small inference and the visual replay are implemented. May–July 2026
QQQ trades are downloaded and validated. The separate trade-feature correction
study is complete: July five-minute MAE was 0.94% worse than candle correction.
July is closed for tuning; August is development. Raw trade replay and an explanation
panel are not yet connected to the app. The app now offers actual trade-dollar
totals for May/June alongside the default approximate amount. This is one
trade-derived field in Kronos's existing candle input, not raw-tape ingestion.
The 12-origin May 1 integration check showed nearly unchanged forecasts; it
does not establish predictive improvement. See `docs/KRONOS_LAB_APP.md`.

The sections below retain the older boundary-probability project history.
Their statements about no fitted models or future next steps describe that
track, not the current Kronos Lab status. Do not treat their old test partitions
as untouched without auditing subsequent use.

## Decisions (Phase 1)

Replay target/stop experiments implemented: fixed 1:1, 2:1, 3:1 reward:risk,
direction from median +5 close, Wilder ATR14 over frozen input window for 1R.
Sampled and observed percentages are separate; complete-window denominator
includes ambiguous results, with pending/incomplete/no-setup separate. No tape
order resolution or execution simulation. Frozen setups and outcomes persist.
Fourteen tests plus browser pending-to-complete and persistence checks pass.
Scout remains close-based. See `docs/KRONOS_LAB_APP.md`.

Replay now displays five-minute predicted/actual high, low and upside/downside
excursions from frozen reference close. Actuals update "so far" and final errors
require all five target minutes. Invalid sampled OHLC paths are excluded from
range summaries with counts shown. Range outcomes persist separately for
packaged Base/Small forecasts. Twelve tests and browser reveal/persistence checks
pass. Scout's close-based target is unchanged.

Smaller companion chronological comparison complete: 7/14/21-feature candidates
tested in two expanding May folds (540 out-of-fold rows). Seven Kronos-output
features selected on May only; all-May fit scored June Brier 0.248374 versus
constant 0.249493. Paired session interval crosses zero; gate MAE still worse
than unchanged. This redesign is post-hoc development, not independent validation.
See `docs/COMPANION_SMALL_V02_RESULTS.md` and `data/companion_small_v02/`.

Companion v0.1 diagnosis complete without refitting: May in-sample gains do not
carry to June; probability ranking/calibration is weak, and removing any single
June session does not restore baseline superiority. Volatility inputs shifted;
exploratory fixed-model substitutions flag higher-timeframe features for review.
See `docs/COMPANION_V01_DIAGNOSIS.md`. Findings are post-hoc, not new validation.

First companion models fitted under frozen `docs/COMPANION_TRAINING_V01.md`:
May-only ridge logistic, candle/Kronos versus same plus trades. On 1,134 June
development origins both had worse Brier scores than May climatology; trade
minus candle Brier difference +0.000491 had a session-bootstrap interval
crossing zero. Neither forecast-selection gate beat always unchanged MAE.
Artifacts: `data/companion_model_v01/`; conclusions and validation in
`docs/COMPANION_MODEL_V01_RESULTS.md`. July untouched; no promotion recommended.

Companion v0.2 expanded to 2,214 existing Base forecasts across 41 May/June
sessions (May 1,080; June 1,134), at the archived five-minute cadence. All rows
have complete candle/trade features and separate labels, with zero exclusions,
null feature values or missing forecasts. Fourteen regression tests and 41
independent session feature/label checks pass. No fitting or July access.
See `docs/COMPANION_MAY_JUNE_BUILD.md` for artifacts and scope.

Companion v0.2 specification and feature builder implemented. The first dry run
reuses 12 May 1 Base forecasts (120 bars, 25 paths, seed 42, approximate amount)
and creates 41 candidate features plus five metadata fields; labels are separate.
All rows have complete audited trade summaries. Fourteen focused tests pass,
including forming-bar exclusion, formula checks, future mutation invariance,
missing-minute rejection and session-close limits. No fitting or July access.
See `docs/COMPANION_FEATURE_SPEC_V02.md` and `data/companion_v02/dry_run_may01/`.

Token comparison complete on 12 May 1 development origins: 11 pairs had
identical tokens and sampled paths; the remaining pair changed one second-
component input token and median closes by at most $0.0009765625.
See `docs/KRONOS_TOKEN_COMPARISON.md`. This is a representation diagnostic,
not evidence of predictive improvement. Random-seed stability is complete on
the same 12 origins with five seeds and 25 paths: mean absolute five-minute
median-close change versus seed 42 was $0.05431; one same-seed repeat was exact.
See `docs/KRONOS_SAMPLING_STABILITY.md`. No app defaults changed.

Current Kronos addition: synchronized input records are implemented for Base
and Small, with audited May/June companion trade summaries and separate revealed
outcome snapshots. See `docs/INPUT_PACKAGES.md`. Eleven focused tests and a
real saved-forecast integration check pass. No new training or July tuning.

- Project root: `C:\Users\ruley\AiStcockProbabilitydoctor` (was empty).
- Package: `level_probability_lab`, CPU-only Python 3.10+, Windows/PowerShell.
- Calendar: NYSE via `pandas_market_calendars`.
- Timestamps stored in UTC. Databento `ts_event` = bar start. Usable time =
  bar_end + assumed publication lag (default 0s).
- Pilot feed: `XNAS.ITCH` `ohlcv-1m` QQQ+NVDA+TSLA, 2026-08-01..2026-09-01.
  Nasdaq TotalView, venue-specific volume (Nasdaq prints only). EQUS.MINI and
  CME futures were quoted then dropped for this first real pull. Prediction
  target remains QQQ; NVDA and TSLA are context.
- Vol scale: sample std of 1-minute log returns on completed lookback bars.
- Boundaries frozen at prediction time: `ref ± k * vol_scale`.
- Nemotron / LLMs: out of scope for Phase 1.
- Databento download: guarded; two approved pulls completed (August pilot and 2018–2026 history).

## Implemented

- Config, local parquet storage, manifests
- Synthetic generator + smoke pipeline
- Normalize / session grid / no_trade vs coverage_gap
- Validation (sort, duplicates, OHLC, volume, UTC)
- Event labels + context as-of join
- Quote-only Databento adapter + guarded download
- pytest suite (30 tests, all passing on 2026-09-17)
- README, AGENTS.md, docs/DATABENTO.md
- Live quote and one approved download have been run:
  `XNAS.ITCH` `ohlcv-1m` QQQ+NVDA+TSLA, 2026-08-01..2026-09-01,
  fingerprint `9e345ac447080e79c55152fa9f7c14ae830acc8426685d437fa251cfb07e2323`,
  quoted cost $0.0355, spending cap $1, state completed.
  Raw: `data/raw/XNAS_ITCH_9e345ac44708.ohlcv-1m.dbn.zst` and `.parquet`.
  Labels: `data/labels/pilot_aug2026/`. A month is a pipeline check, not an edge.
- Multi-year download completed 2026-09-17:
  fingerprint `a0bdd1f87cd32d5ef6c64228866e3be8db21850562b2288ecb45b9b79ada6fa6`,
  `XNAS.ITCH` `ohlcv-1m` NVDA+QQQ+TSLA, 2018-05-01T00:00:00Z..2026-09-01T00:00:00Z,
  fresh get_cost $3.1572, cap $5, 5,044,735 rows.
  Raw: `data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.dbn.zst` and `.parquet`.
  Databento warned of degraded days 2021-07-07, 2021-10-26, 2022-09-19.

## Unresolved / limits

- History file is local; full-history normalize/label and models are not run yet.
- Metadata billing residual uncertainty remains.
- Adapter cannot see or cap Databento’s actual invoice.
- Publication lag is assumed 0s, not measured.
- Prices unadjusted (NVDA/TSLA splits in history).
- No model has been fit. August is development, not holdout.
- Ghost-candle replay (2026-08-14 QQQ): Kronos-small on RTX 5070 via project
  `.venv` cu128, 266 forecasts of 5 minutes / 50 paths. Artifacts in
  `data/ghost_candles/2026-08-14/`. Isolated under
  `src/level_probability_lab/ghost_candles/`. Not a trading signal.
- Direction metric corrected: persistence/zero-change is neutral, not a
  failed direction call. See `docs/GHOST_CANDLE_METRICS.md`. Pooled eval
  across complete local QQQ sessions is `ghost-eval` (append-only ledger
  under `data/ghost_candles/experiments/`).
- Analogue research track (`docs/ANALOGUE_EXPERIMENTS.md`): session-blocked
  Brier/BSS/log loss vs train climatology, leakage `future_end < origin`,
  Kronos interval scale (no weight updates), lookback sweep on 2024 only.
  Commands: `ghost-metrics`, `analogue-sweep`. Do not tune Kronos next.

## Next steps

History file validated: `docs/HISTORY_VALIDATION.md`,
`data/reports/history_validation.json`. Usable for the frozen experiment
with documented halt-day minute gaps, 6 after-hours NaN rows to drop, and
unadjusted TSLA/NVDA splits. Next: label at k in {2,3,4}, then baselines
and trees. Do not score August 2026 as holdout.

See `docs/LABEL_AUDIT.md` and `docs/EXPERIMENT_SPEC.md`.

## Phase map (do not build all at once)

- Phase 2: real-data validation, deliberate history expansion, baseline + trees
- Phase 3: small causal sequence model, walk-forward, holdout, Brier/log loss
- Phase 4: extra context feeds after field-level checks
- Phase 5: paper-trading sim; optional constrained Nemotron assistant; no live trading


## Extended touch tracking (2026-09-19)
The replay now tracks each frozen 1:1, 2:1 and 3:1 setup separately for
five minutes and for up to 60 elapsed minutes, capped at regular session close.
Touch results resolve on the first revealed touching candle; same-minute dual
touches remain ambiguous. Resolution minutes and deadline are saved with each
outcome snapshot (touch-v2). A missing minute before resolution is incomplete;
a gap after a known first touch cannot change that result. Five-minute neither
and extended expired require full coverage through their respective deadlines.
New forecasts never reset previous levels. Extended rates use resolved outcomes,
including expired and ambiguous, while open/missing/no-setup counts are separate.
Early resolutions can bias a running rate; these are exploratory replay counts.
Sampled path percentages still describe five minutes only. Scout is unchanged.
Validation: 16 focused offline tests pass; frontend JavaScript syntax passes.


## Market context v1 (implemented 2026-09-19)
Hourly/daily SMA 5/10/20/50/100/200 and Bollinger 20, population SD x2
are now calculated from completed regular-session candles. Hours anchor at
session open; incomplete final-hour blocks are excluded. Daily bars require
all regular-session minutes. Missing buckets remain null in rolling windows.
History loads 450 calendar days locally; unavailable history stays unknown.
Previous-session high/low and today's high/low so far are also recorded.
Each issued/retrieved forecast saves an immutable context snapshot under
`data/kronos_lab/market_context/`, linked by ID from outcome snapshots. Stored
history evidence contains up to 201 completed buckets per timeframe.

The chart shows selectable horizontal levels frozen at the selected forecast,
not indicator curves; off-screen levels remain available in the table. Context
records signed distances, distance/R, slopes, above/below, and movement toward,
away or across a level from the previous minute close. This is not an intrabar
approach reconstruction. Bands also record position and relative width.

Confluence requires an hourly/daily SMA pair each within 0.5R of price and
within 0.5R of each other. R is the existing frozen Wilder ATR14 setup risk.
This fixed threshold was not optimized. SMA20 slope agreement is separately
recorded. The results-by-location view groups confluence/no-confluence/unknown
for all three ratios and either five-minute or extended tracking. It is pooled
exploration, without matched direction baselines or statistical significance.
Current-session results reset on restart; immutable records stay on disk.
Scout remains offline and unchanged. No fitting, downloads or July scoring.
Validation: 20 focused tests, frontend syntax, and a cached May 1 forecast check
confirm 20 available levels, no future timestamps and an unchanged snapshot
after five-minute reveal. Test outputs: `data/context_integration_check/`.

Browser verification confirmed the saved May forecast context and grouped counts.
An initial no-future-bar pending-state bug was fixed and regression-tested.


## Replay chart upgrade (2026-09-19)
The chart now offers 1-minute, 5-minute, hourly and daily candles, 60/120/240
visible slots, independent indicator timeframe selection, multi-select SMA
5/10/20/50/100/200, Bollinger20 x2 curves, fit-indicators scaling and an expanded
chart layout. Indicator values appear without a forecast; off-screen and
unavailable values are labeled. Optional dashed frozen levels remain distinct
from replay-time indicator curves. Forecast candles display only on 1-minute
charts; switching charts does not change model inputs, targets or replay time.

Hourly/daily candles come from the same regular-session context history. Full
hours anchor at session open and exclude the short closing block. The daily
view excludes the current session until close. Five-minute bars require all five
completed minutes. Missing buckets remain gaps. Indicators use their timeframe's
completed closes; 1m/5m indicators currently have only the loaded session history.
Hourly/daily indicators use the available 450-calendar-day history. Curves retain
missing windows and are joined by availability time, never future timestamps.
Chart slots compress overnight closures. Historical-only; no live feed enabled.

Validation: 22 Python tests pass plus JavaScript aggregation/formula/as-of tests
and syntax checks. Browser verified daily/hourly/5m views and explicit off-screen
labels with no console errors. Chart data is presentation-only and not training.


## TradingView Lightweight Charts replacement (2026-09-19)
Replaced the hand-drawn renderer with TradingView Lightweight Charts 5.2.1,
Apache 2.0. The standalone bundle is pinned locally under lab_web/vendor;
npm SHA512 integrity was verified and the bundle SHA256 recorded in its manifest.
License, official release NOTICE and visible TradingView attribution are retained.
No external chart/data service is contacted at runtime.

Native wheel/pinch zoom, drag panning, crosshair OHLC readout, axis scaling,
zoom buttons, reset and Follow replay are available. Manual chart navigation
turns off following; replay updates preserve the user's viewport when not following.
All already-loaded completed history is available to pan; initial-view count only
sets the starting zoom. Intraday history remains the current replay session.
Timeframes, past-only indicators, frozen levels and blue forecast candles remain.
Forecast dispersion is displayed as dashed p10/p90 close bounds rather than fill.
Indicators default to the displayed chart timeframe; hourly/daily overlays remain
selectable independently. Library code is display-only; no live data enabled.

Rollback: pre-replacement chart.js/app.js/index.html/style.css are preserved in
`data/chart_backups/before_lightweight_charts/`. Restore those four files to
`src/level_probability_lab/lab_web/` to return to the prior renderer; extra vendor
routes/files can remain inert. Model weights, forecast stores and score definitions
were not changed by this replacement. The only server change serves three
explicitly allowlisted local vendor assets.

Validation: 22 offline Python tests pass, including local vendor serving and
path rejection; JavaScript formula/aggregation/as-of and candle-format checks pass.
Browser verified wheel zoom (126 to 114 visible slots), drag panning into earlier
history, zoom buttons (126 to 95 slots), crosshair, daily/hourly/5m/1m views.


## Automated location evaluation v1 completed (2026-09-19)
See `data/location_evaluation_v1/RESULTS.md` and
`docs/LOCATION_EVALUATION_V1_PROTOCOL.md`. Reused 2,214 frozen May/June Base
forecasts across 41 sessions, 120-bar inputs/25 paths/seed42/five-minute cadence.
Scored 1:1/2:1/3:1 for five minutes and up to60/session-close, with always-up,
always-down, momentum5 and exact fair-coin direction controls at matched origins.
No missing forecast origins or incomplete Kronos outcomes. No new inference,
fitting, paid data, or July forecast/outcome access.

Strict 0.5R hourly/daily SMA confluence occurred only five times across two
sessions: four target-first at five-minute 1:1, versus 977/2209 away from
confluence. These five examples cannot establish a reliable advantage. All four
pooled five-minute 1:1 secondary proximity-group excess intervals cross zero.
No Scout promotion/retraining is justified by this run. Next research decision:
predeclare additional development coverage or broader location categories;
do not optimize the threshold to these outcomes. Current chart data flow unchanged.

Artifacts include immutable context JSONL, outcomes/summary/comparisons CSV,
full JSON report, verification and hashes. Eleven focused tests pass. Independent
checks verified all2214 context hashes/cutoffs, 984 late-session control outcomes,
and504 summary denominators. Initial group bootstrap incorrectly conditioned on
sessions containing the group; corrected before delivery to resample all sessions,
including zero-member sessions, as frozen protocol requires. Initial outputs are
preserved under initial_* for audit; no outcomes or point estimates changed.


## Location distance bands v2 completed (2026-09-19)
Report: `data/location_evaluation_v2/RESULTS.md`; fixed protocol:
`docs/LOCATION_EVALUATION_V2_PROTOCOL.md`. Reused the same 2214 May/June
origins and unchanged v1 outcomes; post-hoc development, not fresh validation.
Disjoint 0-0.5R, >0.5-1R, >1-2R and >2R bands for nearest hourly/daily SMA,
hourly/daily BB boundaries and generalized SMA confluence distance. Membership
and coverage were saved before labels were joined. No indicator/threshold search.

Primary five-minute 1:1 hourly-SMA target rates: 42.4% (191 origins), 43.9%
(173), 38.2% (280), 45.7% (1570), respectively. No nearer band establishes a
positive excess over the matched fair-coin control. The >1-2R band has an
exploratory negative association versus >2R; do not promote an avoid-rule from
these already-used data. Daily and confluence near groups remain sparse.
All ratios/windows/monthly tables are saved; Scout and the replay are unchanged.

Five focused tests pass. Independent price-distance and v1-membership checks
cover all2214 contexts; joins, partitions and450 denominators reconcile. Final
artifact hashes verified and v1 files unchanged. No July access, fitting,
inference or download. Next useful evidence would be additional predeclared
development sessions with unchanged categories, not another threshold widening.

## August location expansion v3 completed (2026-09-19)

User approved additional sessions with unchanged rules. Frozen protocol:
`docs/LOCATION_EVALUATION_V3_PROTOCOL.md`; full results:
`data/location_evaluation_v3_august/RESULTS.md`. All 21 August sessions had
390 valid regular-session QQQ bars and 54 origins: 1134 new Base forecasts,
6804 outcome rows. Same Base/tokenizer revisions, 120-bar inputs, approximate
amount, 25 paths/seed42, five-minute cadence, ATR14, SMA/BB categories, ratios,
five-minute and 60-minute/session-close scoring. Inference took 320 seconds.
August was already inspected development, never a new holdout. Completed July
candles were past indicator warmup only; July forecast/outcome archives were
not evaluated. No download, fitting, Scout changes or replay changes.

Overall five-minute 1:1 target-first 521/1134=45.9%, matched coin 43.8%; excess
+2.2pp, session CI [-0.5,+4.8]. Hourly SMA >0.5–1R: 49/86=57.0%, coin45.9%,
excess +11.0pp [1.1,20.0], 18 sessions. Exploratory positive signal, but May40.6%
and June46.2% do not establish stable confirmation; its excess difference versus
>2R crosses zero. Strict confluence 2/8 across4 sessions versus prior4/5 remains
too sparse. No near daily-BB origins. Earlier negative hourly1–2R association
did not clearly repeat. Extended2:1 overall +2.7pp [0.1,5.4] is secondary among
many comparisons. No filter/Scout promotion. Preserve candidate categories;
future confirmation needs an exposure audit and protocol frozen before outcomes.

Contexts/classifications/coverage were persisted before outcome joins. All
1134 context hashes, cutoffs, independent price distances and forecast hashes
verified; 1008 replay-observer comparisons, 27144 independent first-touch
checks, and150 summary rows reconciled. No incomplete Kronos outcomes; neutral
momentum controls remain excluded. Seventeen focused tests pass (sandbox temp
permissions required an approved offline rerun). Earlier v1/v2 artifacts remain
unchanged. Runner: `scripts/run_location_v3.py` phases prepare/forecast/analyze;
completed results are protected against overwrite by the runner.
