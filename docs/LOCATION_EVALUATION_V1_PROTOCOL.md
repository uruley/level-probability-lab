# Location evaluation v1 - frozen development protocol

Frozen before outcome inspection, 2026-09-19. Research only; no model fitting.
Use all archived May/June 2026 Kronos Base forecasts: 120 input bars, 25 paths,
seed42, approximate amount, every five minutes (expected 2,214 origins/41 sessions).
Verify source and reconstructed input hashes against the archive. No July forecast
or outcome access. Earlier historical candles supply indicator warmup only.

Primary grouping: existing market-context-v1 confluence vs no_confluence, with
unknown separate. Hourly/daily SMA5/10/20/50/100/200 pair must each be within
0.5 frozen ATR14 risk units of reference and within 0.5R of each other. Keep
context code and threshold unchanged. Save context before evaluating each origin.
Secondary descriptive groups: proximity within 0.5R to any hourly SMA, daily SMA,
hourly Bollinger boundary, or daily Bollinger boundary (overlapping groups).
No search over periods, thresholds, groups or model settings.

Kronos direction = sign(median sampled +5 close - reference). Neutral has no setup.
For each origin/ratio 1,2,3 and deadline 5 or min(60,session-close) elapsed minutes,
freeze target=reference+direction*ratio*R and stop=reference-direction*R.
Resolve first observed high/low touch; both on the same first touching minute
remain ambiguous. Missing minutes before resolution are incomplete. Record
resolution minutes; neither (5) / expired (60) only after full deadline coverage.

Controls: always up, always down, and sign of trailing five-minute close change
(origin close versus five bars earlier; ties=no setup). Same origins, reference,
R, ratios and deadlines; only direction differs. Fair-coin direction benchmark
is the exact 50/50 average of up/down outcomes, not one random draw. It does
not predict unchanged price (which has no directional barrier setup).

Primary rate denominator includes target, stop, ambiguous and neither/expired;
missing/no-setup are excluded and counted explicitly. Do not report target /
(target+stop) as overall success. Matched excess vs fair-coin uses only origins
where Kronos/up/down all have complete outcomes. Report paired sample size.
Compare confluence-minus-away target rate and the difference in matched excess
between those groups. These are observational comparisons, not causal effects.

Report May, June, and pooled May/June separately. Session-block bootstrap,
2,000 replicates, seed20260919; resample complete sessions with all overlapping
origins together. Compute pooled origin-weighted rates within each draw. Give
95% percentile intervals, valid replicate counts; intervals unavailable with
fewer than two contributing sessions or insufficient usable draws. Report sparse
groups candidly. Multiple ratios/windows/groups are exploratory, unadjusted,
and are not independent confirmation. No win-based selection or promotion.

Artifacts: immutable prediction-time contexts JSONL, per-origin outcome CSV,
summary/comparison CSV and JSON, input/code hashes, coverage and audit report,
and readable RESULTS.md. Replay UI scores remain separate. No new inference,
data purchase, training, live feed or change to July's sealed status.
