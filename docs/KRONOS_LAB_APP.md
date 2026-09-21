# Kronos Lab local app

Run `Start-Kronos-Lab.ps1` from the project folder, or:

```powershell
.\.venv\Scripts\python.exe -m level_probability_lab.lab
```

Open http://127.0.0.1:8765. The server listens only on loopback. Close the
server terminal with Ctrl+C when finished. No data or inference API is used.

## Workflow

1. Choose a session and 60, 120, or 240 completed input candles. Load session.
2. Choose Base, Small, or the saved Small demonstration for August 14, 2026.
3. Generate five future candles. The first GPU request also loads the model.
4. Step one candle, reveal five, or play. Optional automatic forecasting makes
   a forecast before each playback step. Space toggles playback; Right steps
   when focus is outside a form control.
5. Inspect any issued forecast in the comparison table. Restart begins again
   at the selected lookback. Previous immutable forecasts can be reused.

The displayed replay clock is the **end** of the last completed candle.
Candle labels and forecast origin labels use **bar start** timestamps, NY time.
The app displays only revealed actuals; the server retains future prices.
Gaps are not filled. A contiguous input window is required, and five elapsed
forecast minutes must fit before the same session closes. Playback advances
observed candles, so a missing minute creates a visible time gap.

## Models

### Actual traded-dollar input experiment

The Dollar amount input selector offers the original volume-times-close
approximation and actual summed trade price-times-size. Actual totals are
available only on May/June 2026 development sessions. They are grouped by
receive-time minute and checked against the audited candle OHLCV; unavailable
or mismatched totals block the forecast instead of falling back silently.
Other candle inputs, model settings, and seed stay unchanged.

This feeds one trade-derived field into Kronos, not raw tape or side imbalance.
The totals live separately in `data/trade_amount_v1/amounts.parquet`, built
offline with `python -m level_probability_lab.trade_amount`. The completed
trade-correction artifacts are unchanged and July is not used by this mode.
Forecast records retain the amount values and mode; trade-mode cache identity
also includes an input digest. The forecast picker identifies each mode.
The summary score still pools issued forecasts; select individual forecasts
or use the saved comparison report for mode-specific results.

A May 1 development integration check used 12 matching origins, Base, 120
input candles, 25 paths and seed 42. Eleven paired median paths were identical.
Pooled five-horizon MAE was $0.24853756 for approximate amount and $0.24852433
for actual totals. This tiny one-session difference is not evidence of an
improvement. Details and immutable forecasts: `data/trade_amount_v1/development_check/`.

- Base: `NeoQuasar/Kronos-base`, revision
  `2b554741eca47781b64468546e77fef3e85130e6`.
- Tokenizer: `NeoQuasar/Kronos-Tokenizer-base`, revision
  `0e0117387f39004a9016484a186a908917e22426`.
- Small uses the existing pinned local cache from the original project.
- Base weights and tokenizer are cached under `data/models/hub`. On another
  machine, run `.venv/Scripts/python.exe scripts/prepare_kronos_base.py` once.
  This downloads public model files from Hugging Face, not market data.

Inference uses the existing adapter: OHLC, Nasdaq-only volume, approximate
amount = volume × close, and timestamps. The history library is replay data,
not newly trained model knowledge. The LLM interpretation layer is not included.

## Forecast and score semantics

### Target before stop experiments

The replay compares 1:1, 2:1 and 3:1 reward:risk for every issued forecast.
Reference is the last input close; direction is the sign of the all-path median
five-minute close minus reference. Exact neutral means no setup. One R is Wilder
ATR14 calculated only on the frozen input window: first TR=H-L, seed mean of
first 14 ranges, then (13*ATR+TR)/14. It is not an arithmetic rolling mean of
only the latest 14 ranges. Insufficient or degenerate volatility means no setup.

All ratios share the same stop at reference minus direction*R; targets are
reference plus direction*ratio*R. Levels never trail or change after issue.
The five target bars are walked chronologically. First target/stop touch wins;
both within the first touching bar is ambiguous. Opening gaps do not imply a
fill price, and no within-bar ordering is inferred. Trade-tape resolution is
not implemented in this version.

Sampled percentages classify each valid five-candle path using these same
levels; invalid OHLC paths are excluded and counted. Their four percentages
sum to 100 over valid paths, including ambiguous paths. These are uncalibrated
sample frequencies, not Scout probabilities.

Observed percentages classify actual bars only after all five target minutes
are revealed and present. Denominator is all complete setups, including
ambiguous outcomes; target-first, stop-first, neither and ambiguous percentages
are shown with counts. Pending, incomplete and no-setup counts are separate.
Session summaries pool issued engines/settings and overlapping forecasts;
they reset with the replay and are exploratory, not independent observations.

Frozen setups persist under `data/kronos_lab/touch_setups/`, including cached
and saved-demo forecasts. Outcome snapshots include the target/stop setup and
result, with forecast ID and optional input-package ID, under `outcomes/`.
Scout remains the separately tested close-based model. No trade execution,
profit estimate or automatic 70% trigger is added.

The five-minute range panel freezes the origin close as reference and compares
the maximum high and minimum low across the next five elapsed-minute candles.
Upside/downside excursions are max(0, high-reference) and max(0, reference-low).
Each sampled path's extremes are computed first, then their median and 10th/90th
percentiles are displayed. Paths with any invalid OHLC step are excluded from
range summaries, with counts disclosed; raw paths are retained unchanged. If
no valid paths remain, range predictions and errors are unavailable. This
differs from the close table, which retains all raw sampled closes.

Actual range is labeled "so far" until the five target minutes are revealed.
Only complete five-minute windows receive final absolute high/low/excursion
errors; a missing target minute leaves the range incomplete and unscored.
Snapshots persist predicted and observed range metrics in the separate outcomes
files for packaged Base/Small forecasts. Saved-demo outcomes also persist, keyed by forecast ID without an input-package ID. Scout remains close-based and unchanged.

Verified with 12 focused tests and browser playback: 0/5 and 1/5 revealed
showed no final errors, then 5/5 showed final errors; the saved outcome snapshot
contained the same complete five-minute metrics.

Forecast records are appended to `data/kronos_lab/forecasts.jsonl` with input
candles, model revision, sampling settings, seed, raw paths, and issue time.
The model receives only the trailing revealed candles. Identical settings
reuse an existing immutable forecast. Existing research outputs are untouched.

Ghost candles show the sampled path nearest the median close vector. Display
OHLC bounds are repaired if necessary; repair counts are disclosed. The band
shows the pointwise 10th–90th percentiles of sampled **closes**, not calibrated
coverage and not the full high/low envelope.

The table scores median closes against revealed actual closes. Missing outcomes
remain unscored. The baseline holds the origin close constant. Summary MAE pools
the forecast/horizon pairs issued in the current replay, including different
engines if selected. These overlapping observations are not independent, and
interactive selection is not a holdout evaluation. Restart resets this view.

## Verification on 2026-09-19

- RTX 5070: Base generated 25 five-minute sample paths in about 0.84 seconds
  on the first measured inference (model loading excluded).
- Subsequent Base forecasts took about 0.25 seconds each at the same settings;
  Small took about 0.08 seconds. These are spot checks, not a formal benchmark.
- Historical loading checked against May 1, 2018 (390 candles) and the
  July 3, 2024 early close (210 candles).
- Browser: five future actuals hidden before reveal; after Reveal +5 all five
  actuals and errors appeared, with the original forecast unchanged.
- Full offline suite: 71 passing tests, including new server isolation,
  idempotent forecast reuse, input gaps, missing outcomes, session-close bounds,
  and local request protection checks.
- The six new app tests were rerun successfully after adding explicit
  missing-outcome statuses. Browser automatic forecast/play/pause and Base/Small
  switching were also exercised.

Windows sandbox permissions prevented pytest from using its normal temporary
folder; verification used an allowed elevated run with an explicit test folder.


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
# One-hour outlook (2026-09-20)

Use **Forecast one hour** above the chart. This separate experiment always uses
Kronos Base, the selected path count, seed42, and approximate volume-times-close
amount. Its input is 120 completed five-minute regular-session candles spanning
recent sessions; its output is twelve five-minute candles. The main chart can
remain in one-minute candles. The five-minute engine/lookback/amount controls
do not change this hourly input contract.

**Automatically predict the next hour** is on by default. Generate the first
hour forecast, then Play, Step +1 or Reveal +5 will issue the next forecast when
the latest hour ends, using that forecast's path count. Earlier forecasts and
their final scores remain in the hour picker. Playback waits for inference;
it does not use future candles or create duplicate forecasts each minute.
Uncheck the option to stop automatic renewal. No renewal occurs when a full
hour cannot fit before regular-session close. Selecting an older forecast for
inspection does not change the renewal schedule.

Forecasts are available on completed five-minute boundaries with a full hour
remaining before regular-session close. Missing input buckets are not skipped.
The first dates in local history may lack enough prior candles.

Amber shading spans median path-low to median path-high for the full hour;
the amber dot marks median ending close. These are different summary statistics,
not a single sampled path or a calibrated confidence band. Invalid OHLC paths
are excluded from range summaries; raw samples remain saved. Display candle
repairs are counted separately. The overlay can be hidden, and an expandable
detail chart shows the twelve five-minute forecast candles alongside revealed
five-minute actual candles. The overlay appears on the one-minute chart.

Actual high/low updates as minutes are revealed. Final high/low/ending-close
errors and a flat-price ending-close baseline appear after all 60 minutes.
Missing elapsed minutes prevent a final score. These results never enter the
existing five-minute MAE or touch statistics. Inspect earlier hour forecasts
with the separate dropdown; new forecasts do not reset them.

Local append-only predictions: `data/kronos_lab/hour_forecasts.jsonl`.
Separate immutable outcome snapshots: `data/kronos_lab/hour_outcomes/`.
This is a new, unevaluated forecast horizon; previous location studies do not
validate it. Daily forecasting is deferred at the user's request.

## Webull connection

The lab also supports live completed QQQ candles and locally recorded Webull
sessions. See [Webull live setup and limits](WEBULL_LIVE.md). Keep the browser
connected to record; market-closed and stale feeds block live prediction.


## Opening-candle replay (2026-09-20)

Historical and recorded Webull replay now start with the 9:30 Eastern candle,
completed at 9:31 Eastern (8:31 Central), instead of skipping the selected
lookback. Prior regular-session minute candles warm the five-minute model;
exchange-calendar grids permit overnight/weekend closures but reject missing
trading minutes. Live mode uses the same warmup policy. Missing warmup leaves
replay available while prediction waits for enough valid input. No invented bars.
Hourly prediction is available at 9:35 when its separate 120 five-minute input
history is complete. Forecast timestamps retain the real overnight gap.

Cross-session five-minute forecasts use a new prior-session-v1 identity and
freeze their inputs. Opening-hour/later metadata is recorded and shown on the
selected forecast; existing pooled replay scores remain exploratory. Legacy
same-session companion input packages are not created for cross-session windows;
raw forecast records still retain all inputs and sampled paths. Earlier sealed
studies and their window contract are unchanged.

138 offline tests and JavaScript chart/rollover tests passed. Real September18
Webull replay produced a Base forecast at 9:31, an hour forecast at 9:35, and
five scored minute outcomes. Evidence: data/opening_replay_verification.json.
