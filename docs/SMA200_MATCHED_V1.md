# SMA200 matched development comparison v1

Specification frozen before new control outcomes, 2026-09-23.
June is explored development, never a final test. July remains sealed.

Select June archived SMA200 inputs at deterministic 75-minute spacing: earliest
available origin each session, then earliest >=75 minutes later. Only origins
with the entire 75-minute observation window inside the regular session qualify.
Include every selected origin, even already-inside, no-touch or incomplete.
This replaces touch-conditioned encounter selection for the comparison; it
does not overwrite the prior descriptive encounter ledger.

For each case, choose one unused origin on a different June session, within
15 clock minutes, with ATR risk ratio 0.8–1.25. Preserve approach direction
and exact absolute origin-to-level distance in units of the control's own R:
control level = control close - (case close - case SMA)/case R * control R.
Require this hypothetical level to be at least 1 control R from its actual
SMA200. It may coincide with other references, so this specifically tests
SMA200 association rather than all support/resistance. Rank matches by absolute
log risk ratio plus absolute time difference / 15 minutes, then origin string.
Greedy chronological matching; forbid overlapping 75-minute control windows
within a session. Leave unmatched cases explicit; never loosen calipers.
Matching reads frozen inputs only, never subsequent touch/outcome data.

Use unchanged zone ±0.1R, barriers ±0.5R, 60-minute touch search, touch minute
plus next14 for response. Audited receive-time tape resolves all touched cases
and controls. Full-window audit required; quality failures remain incomplete.
Report all candidate categories. Primary descriptive contrast: rejection count
divided by ALL matched candidates, case minus control; no-touch remains in
denominator. Also show continuation and quality counts. This measures combined
touch-and-rejection frequency, not trading profit or conditional bounce skill.

Matched pairs may share calendar sessions on opposite arms. Do not present an
independent-binomial or case-date-only bootstrap interval as valid uncertainty.
Report paired differences and leave inference pending a larger independent
confirmation sample. No training, tuned thresholds or paid calls.

Confirmation eligibility: no existing month is assumed unseen. May/June and
August have been examined; July is unavailable. Reserve the first 20 full
regular sessions beginning 2026-09-24 for FUTURE confirmation only, subject to
provider coverage, tape audit and a no-peeking log. Do not claim these data are
already collected or activate a feed/download. No final-test result yet.
