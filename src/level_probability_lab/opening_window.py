"""Past-only regular-session warmup; never bridge missing trading minutes."""
import numpy as np
import pandas as pd
from .calendar import session_schedule


def session_window(bars, last, lookback):
    last = pd.Timestamp(last)
    schedule = session_schedule(str((last-pd.Timedelta(days=14)).date()), str(last.date()))
    grid = pd.DatetimeIndex([t for r in schedule.itertuples()
                            for t in pd.date_range(r.market_open, r.market_close, freq='min', inclusive='left')
                            if t <= last])[-lookback:]
    available = bars.loc[bars.bar_start <= last].set_index('bar_start')
    if available.index.has_duplicates:
        raise ValueError('Duplicate warmup candles.')
    window = available.reindex(grid)
    values = window[['open', 'high', 'low', 'close', 'volume']]
    if len(window) != lookback or not np.isfinite(values.to_numpy(float)).all() or (values <= 0).any().any():
        raise ValueError('Need complete prior-session warmup; missing trading minutes cannot be skipped.')
    if (values.high < values[['open','close','low']].max(axis=1)).any() or (values.low > values[['open','close']].min(axis=1)).any():
        raise ValueError('Invalid warmup OHLC.')
    window.index.name = 'bar_start'
    return window.reset_index()
