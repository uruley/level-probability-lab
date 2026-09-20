# Companion feature table specification v0.2

Implementation revision of Grok's v0.1 review draft. This version defines the
first development dry run, not a trained model or a new final test.

## Scope and records

One row per frozen Base forecast, 120 same-session completed minute candles,
25 sampled paths, seed 42, approximate dollar amount. The first build reuses
12 May 1 origins spaced 20 minutes apart; it does not generate forecasts for
every minute or the full archive. The feature table has 41 candidate inputs
(34 candle/clock/Kronos inputs plus seven trade inputs) and five metadata fields.
Logistic regression is a future baseline, not part of this implementation.

`origin_id` references the content-addressed input package, including its model
revision, sampled paths, seed, actual input values, amount mode and provenance.
Feature version is stored separately and must join the origin ID in downstream
table keys. Timestamps are UTC; session calculations use the exchange calendar.
No metadata or quality flag is automatically a model input.

## Time and quality contract

All minute intervals are [start, end). Forecast time T is the last completed
bar's end. Feature code sees only bars with end <= T. Five-minute and hourly
bars start at session open, include only complete grids, and never include a
forming bar or a shortened final hour. Earliest default origin is 11:30 NY.
At 10:37, 10:30–10:35 and 09:30–10:30 are complete, but a 120-minute Kronos
forecast is ineligible. The last origin is five minutes before calendar close.

The initial implementation rejects gaps anywhere in the current-session prefix
and incomplete previous sessions. It verifies the last 120 OHLCV inputs against
the frozen forecast. The driver obtains the previous trading session from the
calendar (April 30 for May 1). Prior close means the last Nasdaq candle close,
not a consolidated official closing-auction price. No OHLCV is fabricated.

Trade summaries retain the existing audited receive-time-minute convention.
An event-time rebuild is a separate future experiment. No count of trades that
arrive after T is permitted in features. Only the last five fully valid matched
trade minutes enable the trade block; otherwise all seven trade columns are
null, never zero-filled. Zero activity and missing coverage are different.
The input-package validator enforces availability, quality and OHLCV matching.
The build accesses only May/June trade summaries; July remains closed.

## Exact feature dictionary

C is the last close. ATR is Wilder ATR14 on the complete session prefix: first
true range is H-L; later ranges are max(H-L, abs(H-prevC), abs(L-prevC)). Seed
with the first 14 true ranges' arithmetic mean, then update (13*ATR+TR)/14.
Zero or nonfinite ATR rejects the origin. All signed level distances use
(C-reference)/ATR. All rolling windows below end at the origin and include the
latest completed minute. Price/volume columns are Nasdaq-venue observations.

| Columns | Formula |
|---|---|
| tod_frac_session | elapsed minutes / calendar session length |
| is_near_close, is_half_day | <=30 minutes left; session shorter than 390 minutes |
| dow_ny | Monday=1 through Friday=5; categorical in future fitting |
| ret_1m, ret_5m_sum | last log close return; sum of last five log returns |
| range_1m_atr | (last H-last L)/ATR |
| dist_prev_high_atr, dist_prev_low_atr, dist_prev_close_atr | (C-previous-session reference)/ATR |
| prev_session_range_atr | (previous high-previous low)/ATR |
| dist_sma20_atr, dist_sma50_atr | (C-mean of last n closes)/ATR |
| sma20_slope_atr | (SMA20 now-SMA20 five elapsed minutes ago)/ATR |
| sma50_slope_atr | (SMA50 now-SMA50 ten elapsed minutes ago)/ATR |
| bb_pctb | (C-(SMA20-2*SD20))/(4*SD20), sample SD ddof=1; null at zero SD |
| bb_width_atr | 4*SD20/ATR |
| atr14_over_close | ATR/C |
| rvol_20 | sqrt(sum of squared last 20 one-minute log returns) |
| nasdaq_vol_ratio_20 | latest volume / median of last 20 volumes |
| nasdaq_vol_ratio_5_20 | sum of last 5 volumes / (5*median of last 20) |
| m5_ret_last, m5_ret_prev | log(close/open) of last and penultimate complete five-minute bars |
| m5_range_atr | last complete five-minute (high-low)/ATR |
| m5_clv | (2*close-low-high)/(high-low), null if flat |
| h60_ret_last, h60_range_atr | log(close/open), (high-low)/ATR of last complete 60-minute bar |
| k_d1_atr through k_d5_atr | (median sampled close at horizon-C)/ATR |
| k_path_iqr5_atr | (75th-25th percentile sampled +5 close)/ATR; linear quantiles |
| k_path_frac_up5 | fraction of sampled +5 closes strictly above C |
| ts_n_1m | audited last-minute trade count |
| ts_vwap_dist_atr_1m, ts_vwap_dist_atr_5m | (VWAP-C)/ATR; five-minute VWAP is volume weighted |
| ts_known_signed_fraction_1m, ts_known_signed_fraction_5m | (recorded B volume-recorded A volume)/total volume; five-minute ratio from volume-weighted minute ratios |
| ts_unknown_share_1m, ts_unknown_share_5m | unknown volume / total volume; five-minute value volume weighted |

VWAP is recovered from the audited stored vwap_close_bps and matching close:
close*(1+bps/10000). This is a floating-point reconstruction, not a new tape
aggregation. Recorded side is deliberately not labeled buyer/seller. The signed
fraction differs from Grok's known-volume denominator; preserve this definition
and unknown fraction together. The current loader rejects nonpositive minute
volume, so volume denominators are positive in this dry run.

Near-open is removed because it is always false with a 120-minute window. The
MA-gap column is algebraically redundant with the two MA distances. Ambiguous
hour-volume comparisons, extra band widths, raw price changes and the misleading
`k_beats_unchange_pred` flag are deferred. Running session highs/lows are causal
if computed through T, but are deferred for scope, not classified as leakage.

## Labels and future evaluation

Labels live in a separate parquet file. Require all five target minutes, then
define d = abs(F5-A5)-abs(C-A5). A tie is abs(d)<=1e-8 dollars; tie labels are
null. Otherwise y=1 if d<0 and 0 if d>0. Labels become available at the end of
the fifth target bar. Log the tie rate; probability metrics excluding ties
describe win probability conditional on a non-tie, not unconditional success.

Future fitting must compare candle/Kronos versus candle/Kronos/trades on identical
eligible origins. Use train-fitted win frequency as a probability baseline,
Brier score primary, plus log loss and calibration. Classification accuracy is
secondary. A forecast-selection rule must report one combined MAE across all
origins, not separate subgroup MAEs masquerading as overall improvement.
Freeze its threshold using development data only.

Use session chronological splits, enforce training label availability before
validation starts, fit preprocessing on training only, and estimate uncertainty
by session blocks. May/June are development, July is spent, August is development.
No untouched test period is assigned. Audit both prior local data exposure and
known pretrained-model coverage before making historical out-of-sample claims.
Keep seeds/sample settings fixed and assess seed sensitivity separately; the
recent five-seed diagnostic showed material sampling variation.

## Outputs and acceptance

Run `scripts/build_companion_dry_run.py`. Outputs under
`data/companion_v02/dry_run_may01/`: features.csv, features.parquet, labels.parquet,
input_packages and report.json. Twelve rows are an integration sample, not enough
for fitting or performance claims. The driver verifies future-candle mutation
invariance for every row, package alignment, uniqueness, trade completeness,
and finite feature values. Outcomes are never passed to the feature builder.
