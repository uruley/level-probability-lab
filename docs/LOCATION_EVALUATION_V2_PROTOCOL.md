# Location distance bands v2 - development protocol

Frozen 2026-09-19 before inspecting v2 category outcomes. This is explicitly
post-hoc development motivated by v1's sparse confluence count, not a new holdout.
Reuse only v1's hashed May/June context and outcome ledgers (2,214 origins,
41 sessions). No new predictions, data acquisition, training, or July access.
Preserve v1 and all of its thresholds and reports.

Five location families, evaluated separately:
1. Nearest hourly SMA (5/10/20/50/100/200).
2. Nearest daily SMA (same periods).
3. Nearest hourly Bollinger upper/lower boundary (20 periods, 2 SD).
4. Nearest daily Bollinger upper/lower boundary.
5. SMA confluence distance: minimum over every hourly/daily SMA pair of
   max(abs(price-hourly)/R, abs(price-daily)/R, abs(hourly-daily)/R).
   Thus <=0.5 is exactly the original strict confluence criterion.
For the first four families use the absolute nearest signed distance/R already
saved at prediction time. All required levels must be present; otherwise unknown.
R remains the original frozen one-minute ATR14; do not change the normalization.

Fixed, disjoint bands per family: [0,0.5], (0.5,1], (1,2], (2,infinity), unknown.
No search, adaptive bins, best-period selection or new crossing/approach filters.
Persist classifications and event/session counts BEFORE joining outcome labels.
All bands/families are reported even if empty. Families overlap each other.

Primary view: five-minute 1:1. Report other ratios and extended windows as
secondary descriptions. Inherit first-touch scoring, ambiguity, expiry, deadline
and denominator rules unchanged from v1. Controls: always-up, always-down,
momentum5 and exact fair-coin direction. Compare each band's matched Kronos
excess over fair coin; compare near bands with >2R, both raw target rate and
matched excess. These are associations, not causal estimates.

Report pooled, May and June. Use v1 corrected whole-session bootstrap with
all period sessions included, 2,000 draws and seed20260919. Keep origins within
a session together. Withhold CIs with <2 contributing sessions or <1900 valid
draws. Intervals are exploratory and unadjusted for multiple comparisons.
A descriptive support flag requires >=100 origins/10 sessions pooled AND
>=30 origins/5 sessions in EACH month. This is a sample-coverage flag, not proof
of statistical power, significance or profitability. No automatic promotion.

Artifacts: frozen protocol, classifications.csv, coverage.json (before labels),
joined outcomes.csv, full summary/comparison CSV/JSON, verification, hashes and
RESULTS.md. Compare initial <=0.5 membership to v1. Independently recompute
nearest-level distances from prices for every origin; verify partitions and joins.
Report uncertainty and month-to-month consistency; do not select a winning rule
for Scout on these same already-examined months.
