# Webull live candles and recordings

User-authorized data-only integration, September20,2026. No trading/account
API is imported or called. No subscription is purchased. The existing official
Webull data entitlement was checked successfully with QQQ M1/M5 requests.

## Controls

Select **Live Webull · QQQ** under Data source and click **Connect Webull**.
The open browser polls every15 seconds. It uses completed regular-session
one-minute candles, with a five-second settlement delay; this is not a trade
tick stream. Forecast each new candle is enabled on connection. The existing
hourly-auto checkbox starts an hourly forecast when its inputs/boundary are
available and renews it after expiry. Model execution pauses the polling loop.
Stop live recording stops that browser's polling; closing the page also stops
it. There is no unattended background capture service. Other connected lab
tabs can independently continue polling.

Market-closed or stale feeds disable prediction; candles older than95 seconds
during the regular session are stale. Start-of-session five-minute forecasts
use locally available prior-session minute candles for the selected lookback.
Missing warmup blocks prediction until sufficient completed candles exist. Hourly forecasts need120 valid
completed five-minute bars, a five-minute boundary and a full hour remaining.
They may use previous sessions' Webull warmup bars. Sparse input fails visibly.
All sampled paths/inputs remain frozen. Five-minute/hourly errors stay separate.

Select **Recorded Webull sessions** to replay locally saved bars using the same
chart. This does not contact Webull. Partial recordings are not filled or
invented; a date may lack sufficient lookback. Historical Nasdaq archive mode
remains separate. No Nasdaq trade features or stale Nasdaq daily indicators are
attached to Webull forecasts; unavailable higher-timeframe context is explicit.

## Local connection

scripts/webull_data_worker.py runs in the existing scanner environment:
`C:/Users/ruley/WebullTradingScanner/.venv/Scripts/python.exe`.
It directly instantiates OfficialWebullBackend with production data endpoints.
The lab `.env` supplies `WEBULL_APP_KEY` and `WEBULL_APP_SECRET` when both are
set, and that login keeps its token under `data/kronos_lab/webull_token`.
Otherwise the scanner key and token directory are used. It does
not use the scanner's automatic provider selection, account client, strategy
engine, journal or demo fallback. Credentials are never sent to the browser,
copied into this repo, or returned in worker errors. SDK output is suppressed.
Authorization may require the scanner's existing mobile approval flow; token
cache access is shared. The scanner's source and settings are not changed.

One initial request each for1200 M1 and M5 bars warms the connection; subsequent
requests fetch120 M1 bars. Polls are serialized and throttled across lab tabs.
Completed five-minute candles are aggregated from received one-minute data;
earlier official M5 bars supply warmup. Missing five-minute slots remain NaN.
Price/volume validity, UTC alignment, duplicate timestamps and session boundaries
are checked. Errors stop the UI loop instead of substituting another provider.
The official API subscription is distinct from app subscriptions:
https://developer.webull.com/apis/docs/market-data-api/subscribe-quotes/

## Files and evaluation limits

`data/kronos_lab/webull/snapshots/`: immutable timestamped received responses.
`data/kronos_lab/webull/YYYY-MM-DD.json`: latest regular-session recording.
`data/kronos_lab/webull/five_minute.json`: accumulated hour-model warmup.
Existing forecast/outcome files use Webull-prefixed identities and source labels.
Corrections to received candles update the recording but not frozen inputs;
older responses remain in snapshots. Five-minute IDs include the input hash.

M1 timestamps observed in the connection check ran through19:59UTC and M5
through19:55UTC for the16:00 New York close, consistent with start-labelled bars.
Only completed bars enter prediction. Since polling/inference introduces delay,
creation timestamps can be later than the nominal candle boundary: these are
not instantaneous forecasts or a verified live trading performance claim.
Feed coverage/volume is Webull-specific and should not be assumed identical to
the previous Nasdaq-only archive. September20 is Sunday: market-hours delivery,
latency, reconnection and exchange corrections still need a forward observation.


## Streaming quote panel (2026-09-21)

Connect quotes & time-and-sales starts a separate official QQQ MQTT connection.
The browser refreshes last trade, bid/ask and the latest 60 prints every second.
In Live Webull mode on the one-minute chart an amber partial forming candle
shows received trades. It never enters completed inputs, indicators or scoring.
Provider trade times are Eastern clock strings; side labels are passed through.
This is observed feed coverage, not a verified consolidated tape.

Sanitized quote/snapshot/tick records append under data/kronos_lab/stream by
UTC date, with receive time; latest.json is the display snapshot. Closing or
disconnecting the last panel expires its lease within 30 seconds. This control
is separate from completed-candle recording. No orders or purchases. Live
verification received prices, bid/ask, 60 tape rows and forming OHLC. JavaScript
chart/rollover checks passed. Raw feed records are not deduplicated trade totals.

Level 2 check (2026-09-21, after the regular session): the official subscribe
call accepts a `depth` argument, and quote messages can carry more than one
bid and ask. A request for 10 levels on this OpenAPI app key was rejected
with HTTP 417, `ILLEGAL_PARAMETER`, `depth not more than 1`. The same refusal came back after the lab `.env` secret was reset, and again
at 9:46 AM Eastern on 2026-09-22 while the regular session was open. It is
not an after-hours or overnight limit. This API application allows one level. Level 2 visible on the stocks page is a
separate retail subscription and is not granted to OpenAPI. The stream falls
back to trades, snapshots, and the inside quote. A one-level quote is
recorded as top of book, not as Level 2.


TSLA live support (September21): Live symbol selector switches candle polling,
quote/tick stream and chart labels. TSLA records live under webull/TSLA and
stream/TSLA, with symbol-prefixed forecast identities. QQQ archives remain QQQ.
Both share the local model; each browser chooses its symbol. Changing symbols
stops that tab's prior polling; its old quote lease expires within30 seconds.
Verified official TSLA candles and a real Base five-minute forecast at10:36 NY.


NVDA and latency update (September21): NVDA joins QQQ/TSLA with separate feed,
stream and forecast identities. Chart reset identity includes symbol/provider,
so switching from QQQ resets its manually retained price scale. Live polling
now targets minute-close +6 seconds (retaining the5-second completed-bar guard),
retries missing/stale bars every5 seconds, and waits for the next boundary once
caught up. Feed cache throttle is4 seconds. Recent TSLA inference was~0.25s;
creation latency after candle close was7.65–22.46s before this scheduling change.
Provider publication, request and computation time still add latency; no
instantaneous forecasting claim. Focused feed and JS polling/chart tests pass.
# September 24 symbol expansion

User authorized SPCX (US-listed SpaceX), AMZN and GOOGL in addition to QQQ,
TSLA and NVDA. All six are available in the live selector and recording review.
The three new symbols returned current official Webull candles and valid
400-minute PRE/RTH input windows. They use the existing Kronos model; this
does not establish forecast accuracy on the added symbols. Data-only access;
no orders or subscription purchases. Recordings remain separate by symbol.
