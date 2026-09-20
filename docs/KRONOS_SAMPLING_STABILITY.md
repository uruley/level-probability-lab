# Sampling stability: May development diagnostic

Twelve May 1, 2026 origins matched the token comparison. Each used Base,
120 completed candles, approximate amount, 25 paths, temperature 1.0, top-p
0.9 and top-k 0. Only the seed varied: 42, 43, 44, 45, 46.
No outcomes were scored and no July data was evaluated.

Mean absolute change in the median predicted close relative to seed 42,
averaged over 12 origins and four alternative seeds:

| Horizon | Mean absolute change |
|---|---:|
| +1 minute | $0.02734 |
| +2 minutes | $0.03720 |
| +3 minutes | $0.04668 |
| +4 minutes | $0.04924 |
| +5 minutes | $0.05431 |

The maximum absolute change across all comparisons/horizons was $0.20276.
Repeating seed 42 at the first origin reproduced all sampled OHLC paths exactly
on this machine. This single repeat is not a cross-hardware determinism guarantee.

Sampling variation in these windows was substantially larger than the dollar-
amount substitution's maximum median-close change of $0.00098. That comparison
concerns sensitivity, not predictive accuracy. Neither seed disagreement nor
the sampled bands are calibrated probabilities of being correct.

Keep a fixed seed for reproducible matched experiments. Assess candidate
improvements across several predeclared seeds; never select a seed because
it scores better. Before increasing sample count, measure whether additional
paths reduce variation enough to justify the runtime. Do not change the
completed July study or interpret this one-session diagnostic as general proof.

Script: `scripts/check_kronos_sampling_stability.py`.
Artifacts: `data/trade_amount_v1/sampling_stability/report.json` and
`paths_and_inputs.npz`. All 60 forecast batches were checked against saved
paths and report statistics independently recomputed. There was one additional
inference call for the same-seed repeat. No model weights or app defaults changed.
