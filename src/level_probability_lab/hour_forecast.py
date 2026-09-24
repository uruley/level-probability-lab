"""Separate one-hour forecast experiment: completed 5m inputs, 12 future bars."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .calendar import session_schedule
from .range_metrics import forecast_range


def aggregate(raw, schedule):
    rows=[]
    for session in schedule.itertuples():
        day=raw.loc[(raw.bar_start>=session.market_open)&(raw.bar_start<session.market_close)].set_index('bar_start')
        if day.index.has_duplicates: raise ValueError('Duplicate minute bars in hourly forecast history.')
        for start in pd.date_range(session.market_open,session.market_close,freq='5min',inclusive='left'):
            end=start+pd.Timedelta(minutes=5)
            if end>session.market_close: continue
            block=day.reindex(pd.date_range(start,periods=5,freq='min'))
            a=block[['open','high','low','close','volume']]
            good=np.isfinite(a.to_numpy(float)).all() and (a>0).all().all()
            good=good and (a.high>=a[['open','low','close']].max(axis=1)).all() and (a.low<=a[['open','close']].min(axis=1)).all()
            rows.append(dict(bar_start=start,bar_end=end,
                open=float(a.iloc[0].open) if good else np.nan, high=float(a.high.max()) if good else np.nan,
                low=float(a.low.min()) if good else np.nan, close=float(a.iloc[-1].close) if good else np.nan,
                volume=float(a.volume.sum()) if good else np.nan))
    return pd.DataFrame(rows)


def load_inputs(source,date,days=14):
    start=pd.Timestamp(date)-pd.Timedelta(days=days)
    schedule=session_schedule(str(start.date()),date)
    raw=pd.read_parquet(source,filters=[('symbol','==','QQQ'),
        ('ts_event','>=',schedule.iloc[0].market_open.to_pydatetime()),
        ('ts_event','<',schedule.iloc[-1].market_close.to_pydatetime())])
    return aggregate(raw.rename(columns={'ts_event':'bar_start'}),schedule)


def availability(revealed, minutes=60):
    cutoff=revealed.iloc[-1].bar_end
    if minutes==60 and (cutoff-revealed.iloc[0].session_open).total_seconds()%300:
        return False,'Available at the next completed five-minute boundary.'
    if cutoff+pd.Timedelta(minutes=minutes)>revealed.iloc[0].session_close:
        return False,f'{minutes} minutes must remain in this regular session.'
    return True,''


def input_window(history,revealed):
    ok,reason=availability(revealed)
    if not ok: raise ValueError(reason)
    cutoff=revealed.iloc[-1].bar_end
    window=history.loc[history.bar_end<=cutoff].tail(120).copy()
    if len(window)!=120 or window.iloc[-1].bar_end!=cutoff or not np.isfinite(window[['open','high','low','close','volume']].to_numpy(float)).all():
        raise ValueError('Need 120 complete five-minute candles, including prior sessions; missing bars cannot be skipped.')
    return window.reset_index(drop=True),pd.date_range(cutoff,periods=12,freq='5min')


def public(row,revealed):
    paths=np.asarray(row['sampled_paths'],float)
    start=pd.Timestamp(row['as_of']); end=start+pd.Timedelta(minutes=row.get('horizon_minutes',60))
    clock=revealed.iloc[-1].bar_end
    expected=pd.date_range(start,min(clock,end),freq='min',inclusive='left') if clock>start else pd.DatetimeIndex([],tz='UTC')
    actual=revealed.loc[revealed.bar_start.isin(expected)]
    complete_grid=list(actual.bar_start)==list(expected)
    finished=clock>=end
    status='incomplete' if not complete_grid else 'complete' if finished else 'pending'
    high=float(actual.high.max()) if len(actual) else None
    low=float(actual.low.min()) if len(actual) else None
    close=float(actual.iloc[-1].close) if status=='complete' else None
    predicted=forecast_range(paths,row['reference'])
    median_close=float(np.median(paths[:,-1,3]))
    values=dict(high=high,low=low,close=close)
    estimates=dict(high=predicted['high']['median'] if predicted['high'] else None,
                   low=predicted['low']['median'] if predicted['low'] else None,close=median_close)
    errors={k:abs(v-values[k]) if status=='complete' and v is not None else None for k,v in estimates.items()}
    return dict(id=row['forecast_id'],as_of=row['as_of'],end=end.isoformat(),targets=row['target_timestamps'],
        candles=row['displayed_path'],range=predicted,median_close=median_close,
        close_p10=float(np.quantile(paths[:,-1,3],.1)),close_p90=float(np.quantile(paths[:,-1,3],.9)),
        reference=row['reference'],samples=row['sample_count'],seconds=row['inference_time_s'],
        repairs=row['invalid_ohlc_steps'],cached=row.get('cached',False),
        outcome=dict(status=status,observed_minutes=len(actual),actual=values,errors=errors,
            flat_close_error=abs(close-row['reference']) if close is not None else None))


def save_outcomes(state,output):
    directory=Path(output)/'hour_outcomes'
    for f in state.get('hour_forecasts',[]):
        row=dict(forecast_id=f['id'],revealed_through=state['clock'],outcome=f['outcome'])
        text=json.dumps(row,sort_keys=True,allow_nan=False)
        path=directory/(hashlib.sha256(text.encode()).hexdigest()+'.json')
        directory.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('x',encoding='utf-8') as stream: stream.write(text)
