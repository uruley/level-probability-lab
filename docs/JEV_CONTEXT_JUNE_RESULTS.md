# Unchanged Jev context comparison: June continuation

Same jev-1.13.0, questions, compact schemas, thresholds and archived origin
indices 0/27 per session. Forty-two origins across 21 June sessions, following
the 40 May origins. All 84 new responses validated and were persisted before
outcome scoring. No prompt selection or July access. June is previously explored
development data, not a new sealed test. This expands the study to 82 origins
across 41 sessions; May and June are reported separately.

| June engine | Brier | Log loss |
| --- | --- | --- |
| Kronos Base | 0.446629 | 1.235161 |
| Jev without context | 0.542748 | 1.450603 |
| Jev with context | 0.522943 | 1.416575 |
| Fixed May climatology | 0.481746 | 0.870333 |
| Neutral persistence | 0.571429 | 3.947290 |

Lower is better. Context minus no-context differences: Brier -0.019805,
95% paired session-bootstrap interval [-0.056713, +0.014249]; log loss
-0.034029 [-0.117084, +0.036293]. Neither establishes a context benefit.
Context minus Kronos: Brier +0.076314 [+0.003501, +0.153364]; log loss
+0.181413 [+0.019447, +0.368381]. Both are worse in this study. These remain
exploratory intervals conditional on previously explored data, not independent
proof or calibrated market probabilities. No promotion recommended.

Outcomes: six bull, thirty neutral, six bear. Analogue comparison unavailable.
All selected context/forecast hashes and availability checks passed. No live
receipt-latency claim follows from historical bar timestamps.

141,322 input tokens, estimated $0.005935524 under the $0.25 batch cap.
Pricing rechecked at https://docs.typesafe.ai/models ($0.042/M input, output
free). Cost is a published-rate estimate, not an account receipt. Max 84
requests; exclusive per-request reservations and no uncertain retries.

Artifacts: `data/jev_context_june_v1/manifest.json`, `execution_june.json`,
saved request/response files and `report.json`. Prepare with
`scripts/freeze_jev_context.py --june`; `scripts/test_jev_context.py --june`
reproduces scores offline. Cached replay verified. 23 focused offline tests
pass. No chart changes or continuous Jev polling enabled.
