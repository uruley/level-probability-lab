# Live Jev observer

Live QQQ only. Refresh the lab, reconnect live QQQ, then enable the observer
panel at the bottom of the page. Off by default on process restart. Each new
completed-minute Kronos prediction may submit one background Jev request;
historical/replayed or over-one-minute-old origins cannot trigger requests.
One in-flight request at a time; busy origins are skipped, not queued.

The panel shows Kronos/Jev experimental scores and matured five-minute class.
No calibrated probability or trading claim. Actual outcomes require all five
target bars; gaps are incomplete. Polling the live feed also persists outcomes.
Available market levels accompany the compact forecast; missing higher-timeframe
Webull context is not reconstructed. Current live feed may only supply session
levels. Non-QQQ data cannot score QQQ records.

Records in `data/kronos_lab/jev_live/<date>/<minute>/` survive restarts.
The $0.25 daily cap conservatively reserves $0.002752512 per request based on
65,536 input tokens at $0.042/M, output free (verified TypeSafe model pricing
September 23). No refunds to reservations; at most 90 calls/day before shutdown.
An entire regular session may therefore stop early even if actual token cost
is much lower. Off prevents future calls; in-flight requests may finish.
Failures remain unavailable and are never automatically retried. Enablement
is local-process state, shared across QQQ tabs; reservations are durable.
Only one lab server should use this output directory. Pricing must be rechecked
if provider rates change. This is a local bound, not a provider billing limit.

21 focused offline tests pass; JavaScript syntax verified. Server restarted
and catalog/observer script checked. Real live-minute behavior has not yet
been observed in this implementation turn. No API requests were made by tests.
