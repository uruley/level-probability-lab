"""Past-only higher-timeframe context, separate from Kronos inputs."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .calendar import session_schedule
from .touch_experiment import setup, summary

PERIODS = (5, 10, 20, 50, 100, 200)
VERSION = 'market-context-v1'
NEAR_R = 0.5  # fixed descriptive threshold, not selected on outcomes


def aggregate(raw, schedule):
    """Keep missing buckets as NaN so rolling windows cannot skip data gaps."""
    daily, hourly = [], []
    for session in schedule.itertuples():
        opening, closing = session.market_open, session.market_close
        bars = raw.loc[(raw.bar_start >= opening) & (raw.bar_start < closing)]
        def bucket(start, end):
            b = bars.loc[(bars.bar_start >= start) & (bars.bar_start < end)]
            expected = pd.date_range(start, end, freq='min', inclusive='left')
            good = (list(b.bar_start) == list(expected) and
                    np.isfinite(b[['open','high','low','close']].to_numpy()).all() and
                    (b.high >= b[['open','close','low']].max(axis=1)).all() and
                    (b.low <= b[['open','close']].min(axis=1)).all())
            return dict(start=start, end=end, open=float(b.iloc[0].open) if good else np.nan,
                        volume=float(b.volume.sum()) if good and 'volume' in b else np.nan, close=float(b.iloc[-1].close) if good else np.nan,
                        high=float(b.high.max()) if good else np.nan,
                        low=float(b.low.min()) if good else np.nan)
        daily.append(bucket(opening, closing))
        start = opening
        while start + pd.Timedelta(hours=1) <= closing:
            end = start + pd.Timedelta(hours=1)
            hourly.append(bucket(start, end))
            start = end
    return {'daily': pd.DataFrame(daily), 'hourly': pd.DataFrame(hourly)}


def load_history(source, date):
    end = pd.Timestamp(date) + pd.Timedelta(days=1)
    start = pd.Timestamp(date) - pd.Timedelta(days=450)
    raw = pd.read_parquet(source, filters=[('symbol','==','QQQ'),
        ('ts_event','>=',start.tz_localize('UTC').to_pydatetime()),
        ('ts_event','<',end.tz_localize('UTC').to_pydatetime())])
    raw = raw.rename(columns={'ts_event':'bar_start'}).sort_values('bar_start')
    return aggregate(raw, session_schedule(str(start.date()), date))


def snapshot(history, visible, risk, direction=None):
    cutoff = visible.iloc[-1].bar_end
    price = float(visible.iloc[-1].close)
    previous = float(visible.iloc[-2].close) if len(visible)>1 else price
    levels = []
    def add(name, timeframe, value, stamp=None, slope=None):
        value = float(value) if value is not None and np.isfinite(value) else None
        distance = price-value if value is not None else None
        dr = distance/risk if distance is not None and risk and risk>0 else None
        approach = None
        if value is not None:
            old_distance = previous-value
            approach = ('crossed' if old_distance*distance<0 else
                        'toward' if abs(distance)<abs(old_distance) else
                        'away' if abs(distance)>abs(old_distance) else 'unchanged')
        levels.append(dict(name=name,timeframe=timeframe,value=value,
            available_at=stamp.isoformat() if stamp is not None else None,
            distance=distance,distance_r=dr,near=abs(dr)<=NEAR_R if dr is not None else None,
            side='above' if distance is not None and distance>0 else 'below' if distance is not None and distance<0 else 'at' if distance==0 else None,
            approach=approach, slope=float(slope) if slope is not None and np.isfinite(slope) else None))
    bands = {}
    evidence = {}
    for timeframe in ('hourly','daily'):
        frame = history.get(timeframe, pd.DataFrame()) if history else pd.DataFrame()
        frame = frame.loc[frame.end<=cutoff] if not frame.empty else frame
        evidence[timeframe] = [dict(end=r.end.isoformat(), close=float(r.close) if np.isfinite(r.close) else None, high=float(r.high) if np.isfinite(r.high) else None, low=float(r.low) if np.isfinite(r.low) else None) for r in frame.tail(201).itertuples()]
        closes = frame.close if not frame.empty else pd.Series(dtype=float)
        stamp = frame.iloc[-1].end if len(frame) else None
        for period in PERIODS:
            avg=closes.rolling(period).mean()
            value=avg.iloc[-1] if len(avg) else None
            slope=avg.iloc[-1]-avg.iloc[-2] if len(avg)>1 else None
            add(f'SMA {period}',timeframe,value,stamp,slope)
        mean=closes.rolling(20).mean().iloc[-1] if len(closes) else np.nan
        std=closes.rolling(20).std(ddof=0).iloc[-1] if len(closes) else np.nan
        lower,upper=mean-2*std,mean+2*std
        add('BB lower',timeframe,lower,stamp)
        add('BB upper',timeframe,upper,stamp)
        bands[timeframe] = dict(position=float((price-lower)/(upper-lower)) if np.isfinite(std) and std>0 else None,
            width_fraction=float((upper-lower)/mean) if np.isfinite(mean) and mean>0 and np.isfinite(std) else None)
        if timeframe=='daily':
            past=frame.loc[frame.end<visible.iloc[0].session_open] if len(frame) else frame
            for name,key in [('Previous high','high'),('Previous low','low')]:
                add(name,'daily',past.iloc[-1][key] if len(past) else None,past.iloc[-1].end if len(past) else None)
    complete = list(visible.bar_start)==list(pd.date_range(visible.iloc[0].session_open,cutoff,freq='min',inclusive='left'))
    add('Session high so far','session',visible.high.max() if complete else None,cutoff)
    add('Session low so far','session',visible.low.min() if complete else None,cutoff)
    h=[v for v in levels if v['timeframe']=='hourly' and v['name'].startswith('SMA')]
    d=[v for v in levels if v['timeframe']=='daily' and v['name'].startswith('SMA')]
    pairs=[dict(hourly=a['name'],daily=b['name']) for a in h for b in d
           if a['near'] and b['near'] and abs(a['value']-b['value'])<=NEAR_R*risk]
    known=all(v['value'] is not None for v in h+d) and bool(risk and risk>0)
    slopes=[v['slope'] for v in h+d if v['name']=='SMA 20']
    agreement=('up' if all(v>0 for v in slopes) else 'down' if all(v<0 for v in slopes) else 'mixed') if len(slopes)==2 and all(v is not None for v in slopes) else 'unknown'
    return dict(version=VERSION,as_of=cutoff.isoformat(),reference=price,risk=risk,
        near_threshold_r=NEAR_R,levels=levels,bands=bands,history_evidence=evidence,confluence_pairs=pairs,
        location_group='confluence' if pairs else 'no_confluence' if known else 'unknown',
        trend_agreement=agreement,kronos_direction=direction,
        convention='RTH; hours anchored at session open; partial final hour excluded; completed bars only; SMA; BB20 population SD x2')


def save_context(context, forecast_id, output):
    payload=dict(forecast_id=forecast_id,context=context)
    text=json.dumps(payload,sort_keys=True,allow_nan=False)
    identity=hashlib.sha256(text.encode()).hexdigest()
    directory=Path(output)/'market_context';directory.mkdir(parents=True,exist_ok=True)
    path=directory/(identity+'.json')
    if not path.exists():
        with path.open('x',encoding='utf-8') as f:f.write(text)
    return identity


def location_summary(forecasts):
    result=[]
    for group in ('confluence','no_confluence','unknown'):
        subset=[f for f in forecasts if (f.get('market_context') or {}).get('location_group','unknown')==group]
        result.append(dict(group=group,forecasts=len(subset),five_minute=summary(subset),extended=summary(subset,True)))
    return result
