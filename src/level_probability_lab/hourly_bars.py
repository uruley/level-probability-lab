"""Full regular-session hours from complete five-minute bars; no short tails."""
import numpy as np
import pandas as pd
from .calendar import session_schedule


def hours(history, cutoff):
    cutoff=pd.Timestamp(cutoff)
    schedule=session_schedule(str(history.bar_start.min().date()),str(cutoff.date()))
    indexed=history.set_index('bar_start')
    if indexed.index.has_duplicates:raise ValueError('Duplicate five-minute history.')
    rows=[]
    for r in schedule.itertuples():
        for start in pd.date_range(r.market_open,r.market_close,freq='60min',inclusive='left'):
            end=start+pd.Timedelta(hours=1)
            if end>r.market_close or end>cutoff:continue
            block=indexed.reindex(pd.date_range(start,periods=12,freq='5min'))
            values=block[['open','high','low','close','volume']]
            good=np.isfinite(values.to_numpy(float)).all() and (values>0).all().all()
            rows.append(dict(bar_start=start,bar_end=end,
                open=float(values.iloc[0].open) if good else np.nan,
                high=float(values.high.max()) if good else np.nan,
                low=float(values.low.min()) if good else np.nan,
                close=float(values.iloc[-1].close) if good else np.nan,
                volume=float(values.volume.sum()) if good else np.nan))
    return pd.DataFrame(rows,columns=['bar_start','bar_end','open','high','low','close','volume'])


def inputs(history, cutoff):
    frame=hours(history,cutoff)
    window=frame.tail(60).copy()
    if len(window)!=60 or not np.isfinite(window[['open','high','low','close','volume']].to_numpy(float)).all():
        raise ValueError('Need 60 complete hourly candles; missing hours cannot be skipped.')
    # Anchor to the last completed hour; later partial candles never enter input.
    origin=window.iloc[-1].bar_end
    schedule=session_schedule(str(origin.date()),str((origin+pd.Timedelta(days=14)).date()))
    targets=[]
    for r in schedule.itertuples():
        for start in pd.date_range(r.market_open,r.market_close,freq='60min',inclusive='left'):
            if start>=origin and start+pd.Timedelta(hours=1)<=r.market_close:targets.append(start)
    if len(targets)<5:raise ValueError('Not enough future session hours.')
    return window.reset_index(drop=True),pd.DatetimeIndex(targets[:5]),frame


def display(frame):
    return [dict(time=int(r.bar_start.timestamp()),**({k:float(getattr(r,k)) for k in ['open','high','low','close']} if pd.notna(r.close) else {})) for r in frame.itertuples()]
