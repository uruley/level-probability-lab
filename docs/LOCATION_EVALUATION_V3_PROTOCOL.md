# August location replication v3

Frozen before generating/scoring this expansion, 2026-09-19. Use all 21 regular
QQQ sessions August 3–31, 2026: 54 eligible origins each, 1,134 total. August was
previously inspected and is development, not an untouched holdout. May/June v2
is the reference. Do not select days by results or modify the old studies.

Use the existing local Nasdaq minute source and cached Kronos Base revision
2b554741eca47781b64468546e77fef3e85130e6; tokenizer revision
0e0117387f39004a9016484a186a908917e22426. Last 120 completed same-session bars,
five one-minute forecasts, 25 paths, seed 42 for each origin, temperature 1,
top-p 0.9, top-k 0, maximum context 512, clip 5. Approximate amount is
volume times close, as in the May/June baseline. Origin starts at open+119
minutes and repeats every five minutes through close-6 minutes. No fitting.

Inherit v1 first-touch scoring and v2 location rules unchanged: hourly/daily
SMAs 5/10/20/50/100/200; Bollinger boundaries 20 periods, two population SDs;
completed buckets only; frozen ATR14 R; five location families, distance bands
[0,0.5], (0.5,1], (1,2], (2,infinity), unknown. Preserve same-bar ambiguity,
missing data, neutral setups, five-minute neither and 60-minute/session-close
expiry. Targets and stops remain frozen per origin, with 1:1, 2:1, 3:1 ratios.
No proximity filtering of Kronos inputs or predictions. Freeze all context
classifications and coverage before joining any August outcome labels.

Primary: five-minute 1:1, all five families/all bands. Other ratios and the
extended deadline are secondary. Compare with always-up/down, momentum5 and
exact matched fair-coin direction. Report raw target rates, excess over coin,
and each near band's raw/excess difference versus >2R. Report August separately
alongside unchanged May/June reference; do not hide differences by pooling.
Whole-session bootstrap: all 21 dates including zero-member days, 2,000 draws,
seed 20260919; fewer than two contributing sessions or 1,900 valid draws means
no interval. Intervals remain exploratory, unadjusted for multiple comparisons.
Report raw coverage for every group. Carry forward v2's support rule across
May, June AND August: >=100 origins/10 sessions overall and >=30 origins/5
sessions in each month. This descriptive flag is not proof of power or an
automatic rule/model promotion criterion.

July forecast and outcome archives remain untouched. Completed July historical
candles may be used strictly as past warmup for August hourly/daily indicators;
no July forecast scoring, threshold selection or retuning. No paid downloads,
live feeds, Scout retraining or chart changes.

Save source/config/code hashes, exact origin list, exclusive forecast files,
context and classification ledgers, coverage, six outcome rows per origin,
complete summary/comparison tables, checks and RESULTS.md. Verify input hashes,
as-of timestamps, independent price-distance formulas, forecast shapes, full
session coverage, and first/last origins against replay scoring. Preserve
existing outputs on restart and reject changed configuration/source/code.
