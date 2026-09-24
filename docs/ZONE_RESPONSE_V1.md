# Candidate-area response pilot v1

Frozen before this pilot's outcomes: first archived context per May 2026
session (11:30 New York cutoff); previous-day high, previous-day low and
hourly SMA20. Use saved level and ATR risk R, never later moving levels.
Zone is level +/-0.1R. Origins already inside the zone are `already_inside`.
Watch the next 60 elapsed minutes for the first bar intersecting the zone.
Approach side is fixed by the origin close. From above, rejection is level+0.5R
and continuation level-0.5R; reverse from below. These are descriptive price
barriers, not orders or fill assumptions. No-touch and gap-over-zone differ.

Observe the touch minute and next 14 elapsed minutes. If the touch bar reaches
either barrier, mark ambiguous: OHLC does not establish post-touch order.
Thereafter the first barrier wins; both in a minute is ambiguous. Missing or
ineligible minutes before resolution are incomplete. No barrier by expiry is
unresolved. Session-end truncation is incomplete. No synthetic fills, profit
estimates, tuned thresholds, or probability claims.

Volume is audited Nasdaq-only traded shares and trade count for the WHOLE
touch minute, plus its ratio to mean volume of the previous 20 complete minutes.
It is not traded volume specifically inside the narrow zone, consolidated volume,
resting liquidity, or proof of absorption. Raw-tape price-bin measurement remains
future work. No July, API calls, model training, or chart-server changes.

Persist all 60 candidate records, frozen inputs separately from observations,
with artifact hashes. Present every event including no-touch and quality states.
This is a workflow pilot on previously explored May data, not evidence of edge.
