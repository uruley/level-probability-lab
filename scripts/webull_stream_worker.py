"""Official Webull quote, trade, and snapshot stream. No order or account calls.

Quote records keep every bid and ask level the feed sends. Missing levels stay
empty. The top of book is never copied downward to look like Level 2.
"""
import json


DEPTH_LEVELS = 10
SUB_TYPES = ['QUOTE', 'SNAPSHOT', 'TICK']


def book_levels(levels):
    rows = []
    for index, level in enumerate(levels or []):
        price = getattr(level, 'price', None)
        if price is None or price == '':
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price != price:
            continue
        size = getattr(level, 'size', None)
        try:
            size = None if size is None else float(size)
        except (TypeError, ValueError):
            size = None
        if size is not None and size == size and size.is_integer():
            size = int(size)
        rows.append({'level': index, 'price': price, 'size': size})
    return rows


def quote_record(quote, received_at):
    bids = book_levels(getattr(quote, 'bids', None))
    asks = book_levels(getattr(quote, 'asks', None))
    return {
        'received_at': received_at,
        'type': 'QuoteResult',
        'bid': bids[0]['price'] if bids else None,
        'ask': asks[0]['price'] if asks else None,
        'bids': bids,
        'asks': asks,
    }


def apply_quote(state, quote, received_at):
    record = quote_record(quote, received_at)
    state['bid'] = record['bid']
    state['ask'] = record['ask']
    state['received_at'] = received_at
    if state.get('level2') != 'rejected':
        if len(record['bids']) > 1 or len(record['asks']) > 1:
            state['level2'] = 'received'
        elif (record['bids'] or record['asks']) and state.get('level2') != 'received':
            state['level2'] = 'top_of_book_only'
    state['level2_bids'] = len(record['bids'])
    state['level2_asks'] = len(record['asks'])
    return record


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, allow_nan=False) + '\n')


def depth_status(status_code):
    """200 accepts the depth request. Anything else is not a book."""
    return 'requested' if status_code == 200 else 'rejected'


def main():
    import contextlib
    import io
    import logging
    import sys
    import threading
    import time
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path
    from zoneinfo import ZoneInfo

    from webull.data.data_streaming_client import DataStreamingClient

    logging.disable(logging.CRITICAL)
    sys.path.insert(0, 'C:/Users/ruley/WebullTradingScanner')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from scanner.webull_client import _ensure_official_sdk_version
    from webull_env import webull_credentials
    _ensure_official_sdk_version()
    app_key, app_secret, token_dir = webull_credentials()

    symbol = sys.argv[1] if len(sys.argv) > 1 else 'QQQ'
    if symbol not in ('QQQ', 'TSLA', 'NVDA', 'SPCX', 'AMZN', 'GOOGL'):
        raise ValueError('Unsupported symbol')
    out = Path(__file__).resolve().parents[1] / 'data/kronos_lab/stream'
    if symbol != 'QQQ':
        out = out / symbol
    out.mkdir(parents=True, exist_ok=True)
    state = {'symbol': symbol, 'connected': False, 'subscribed': False, 'ticks': [], 'forming': None, 'level2': 'pending'}
    lock = threading.RLock()

    def request_stream(client):
        # The connect callback holds an SDK lock. Subscribe after it returns.
        time.sleep(0.05)
        from webull.data.quotes.market_streaming_data import MarketDataStreaming
        streaming = MarketDataStreaming(client.api_client)
        session_id = client.get_session_id()
        try:
            response = streaming.subscribe(session_id, [symbol], 'US_STOCK', SUB_TYPES, DEPTH_LEVELS)
            code = getattr(response, 'status_code', None)
        except Exception:
            code = None
        with lock:
            if depth_status(code) == 'requested':
                state['subscribed'] = True
                state['level2'] = 'requested'
                return
            state['level2'] = 'rejected'
            state['level2_note'] = 'Depth subscribe was not accepted. This feed allows only the top of book. Recording trades and the inside quote only.'
        try:
            response = streaming.subscribe(session_id, [symbol], 'US_STOCK', SUB_TYPES)
            accepted = getattr(response, 'status_code', None) == 200
        except Exception:
            accepted = False
        with lock:
            if accepted:
                state['subscribed'] = True
            else:
                state['error'] = 'Stream subscription failed. Reconnect to retry.'

    def connected(client, *args):
        state['connected'] = True
        threading.Thread(target=request_stream, args=(client,), daemon=True).start()

    def subscribed(*args):
        state['subscribed'] = True

    def message(client, topic, q):
        now = time.time()
        kind = type(q).__name__
        with lock:
            event = {'received_at': now, 'type': kind}
            if kind == 'TickResult':
                event.update(time=str(q.time), price=float(q.price), size=q.volume, side=str(q.side or 'unknown'))
                state['ticks'] = (state['ticks'] + [event])[-60:]
                state['price'] = event['price']
                state['last_trade_received'] = now
                try:
                    raw = float(q.time)
                    seconds = raw / 1000 if raw > 1e12 else raw
                except (ValueError, TypeError):
                    text = str(q.time)
                    if len(text) == 8:
                        seconds = datetime.combine(
                            datetime.now(ZoneInfo('America/New_York')).date(),
                            datetime.strptime(text, '%H:%M:%S').time(),
                            tzinfo=ZoneInfo('America/New_York'),
                        ).timestamp()
                    else:
                        seconds = datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
                minute = int(seconds // 60) * 60
                forming = state['forming']
                if abs(seconds - now) < 90:
                    if forming is None or minute > forming['time']:
                        forming = {'time': minute, 'open': event['price'], 'high': event['price'], 'low': event['price'], 'close': event['price']}
                    if minute == forming['time']:
                        forming['high'] = max(forming['high'], event['price'])
                        forming['low'] = min(forming['low'], event['price'])
                        forming['close'] = event['price']
                    state['forming'] = forming
            elif kind == 'QuoteResult':
                event = apply_quote(state, q, now)
            elif kind == 'SnapshotResult':
                event.update(price=float(q.price) if q.price else None, time=str(q.last_trade_time))
            else:
                return
            state['received_at'] = now
            append_jsonl(out / (datetime.now(timezone.utc).strftime('%Y-%m-%d') + '.jsonl'), event)

    def run():
        try:
            client.connect_and_loop_forever(logger_enable=False)
        except Exception:
            state['error'] = 'Stream connection failed. Reconnect to retry.'

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        client = DataStreamingClient(
            app_key, app_secret, 'us', 'kronos-' + uuid.uuid4().hex[:12],
            http_host='api.webull.com', mqtt_host='data-api.webull.com')
        token_dir.mkdir(parents=True, exist_ok=True)
        client.api_client.set_token_dir(str(token_dir))
        client.api_client._stream_logger_set = True
        client.api_client._file_logger_set = True
        client.on_connect_success = connected
        client.on_subscribe_success = subscribed
        client.on_quotes_message = message
        threading.Thread(target=run, daemon=True).start()
        while time.time() - (out / 'lease').stat().st_mtime < 30:
            with lock:
                tmp = out / 'latest.tmp'
                tmp.write_text(json.dumps(state), encoding='utf-8')
                tmp.replace(out / 'latest.json')
            time.sleep(.5)
        client.disconnect()


if __name__ == '__main__':
    main()
