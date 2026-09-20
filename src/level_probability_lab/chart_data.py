"""Read-only chart series. All transmitted candles end at/before replay time."""
import json
import pandas as pd
from .market_context import PERIODS


def prepare(history):
    result = {}
    for name, source in (history or {}).items():
        frame = source.copy()
        if frame.empty or 'start' not in frame:
            continue
        for n in PERIODS:
            frame[f'sma{n}'] = frame.close.rolling(n).mean()
        sd = frame.close.rolling(20).std(ddof=0)
        frame['bbUpper'] = frame.sma20 + 2*sd
        frame['bbLower'] = frame.sma20 - 2*sd
        result[name] = frame
    return result


def payload(prepared, cutoff):
    result = {}
    for name, frame in prepared.items():
        visible = frame.loc[frame.end <= cutoff].rename(columns={
            'start':'t','open':'o','high':'h','low':'l','close':'c','volume':'v'})
        # pandas serializes NaN as null, never invented candles or zero prices.
        result[name] = json.loads(visible.to_json(orient='records',date_format='iso'))
    return result
