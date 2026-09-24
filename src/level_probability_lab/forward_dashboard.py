"""Read-only local recording review; no feed, inference, or order calls."""
import hashlib
import json
from collections import defaultdict
import numpy as np
import pandas as pd
from .opening_window import session_window
from .range_metrics import forecast_range
from .touch_experiment import setup, observe, summary


def freeze_context(visible, warmup=None):
    cutoff=visible.iloc[-1].bar_end
    opening=visible.iloc[0].session_open
    expected=pd.date_range(opening,cutoff,freq='min',inclusive='left')
    good=list(visible.bar_start)==list(expected)
    vwap=None
    if good and np.isfinite(visible[['high','low','close','volume']]).all().all() and (visible.volume>=0).all() and visible.volume.sum()>0:
        vwap=float((((visible.high+visible.low+visible.close)/3)*visible.volume).sum()/visible.volume.sum())
    sma=None
    try:
        history=pd.concat([warmup,visible]) if warmup is not None else visible
        sma=float(session_window(history,visible.iloc[-1].bar_start,200,premarket=visible.iloc[-1].get("session_policy")=="pre-rth-v1").close.mean())
    except ValueError:pass
    return dict(version='forward-context-v2',session_policy=visible.iloc[-1].get('session_policy','rth'),as_of=cutoff.isoformat(),session_vwap_approx=vwap,sma200=sma,
                convention='HLC3 VWAP from configured session open; 200 completed configured-session one-minute closes; missing history unavailable')


def score(row,bars,now):
    targets=pd.to_datetime(row['target_timestamps'],utc=True)
    deadline=targets[-1]+pd.Timedelta(minutes=1)
    seen=bars[bars.bar_start.isin(targets)].sort_values('bar_start')
    seen=seen[seen.bar_start+pd.Timedelta(minutes=1)<=now]
    complete=list(seen.bar_start)==list(targets)
    status='complete' if complete else 'incomplete' if now>=deadline else 'pending'
    predicted=np.median(np.asarray(row['sampled_paths'],float)[:,:,3],axis=0)
    reference=row['input_window'][-1]['close'];ranges=forecast_range(row['sampled_paths'],reference)
    actual=dict(zip(seen.bar_start,seen.close))
    created=row.get('forecast_created_at')
    # A forecast saved after its first target minute ended was not available in time.
    prospective=bool(created and pd.Timestamp(created)<targets[0]+pd.Timedelta(minutes=1))
    touch=observe(setup(row),row['target_timestamps'],bars) if len(bars) else []
    for t in touch:
        if t['status']=='pending' and now>=deadline:t['status']='incomplete'
    return dict(id=row['forecast_id'],origin=row['last_input_timestamp'],created_at=created,status=status,
        prospective=prospective,context=row.get('forward_context'),
        settings=f"{row['model_name'].split('/')[-1]} · {row.get('lookback')} bars · {row.get('session_policy','rth')} · {row.get('sample_count')} paths · {row.get('model_revision','unknown')}",
        close_error=abs(float(predicted[-1])-float(seen.iloc[-1].close)) if complete else None,
        baseline_error=abs(reference-float(seen.iloc[-1].close)) if complete else None,
        high_error=abs(ranges['high']['median']-float(seen.high.max())) if complete and ranges['high'] else None,
        low_error=abs(ranges['low']['median']-float(seen.low.min())) if complete and ranges['low'] else None,
        predicted_high=ranges['high']['median'] if ranges['high'] else None,predicted_low=ranges['low']['median'] if ranges['low'] else None,
        actual_high=float(seen.high.max()) if complete else None,actual_low=float(seen.low.min()) if complete else None,
        minutes=[dict(time=t.isoformat(),predicted=float(p),actual=float(actual[t]) if t in actual else None) for t,p in zip(targets,predicted)],touch_outcomes=touch)


def dashboard(output,rows,symbol,date,now=None):
    if symbol not in ('QQQ','TSLA','NVDA','SPCX','AMZN','GOOGL'):raise ValueError('Unsupported symbol')
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    folder=output/'webull'
    if symbol!='QQQ':folder=folder/symbol
    dates=sorted(p.stem for p in folder.glob('????-??-??.json'))
    date=date or (dates[-1] if dates else None)
    if date is not None and date not in dates:raise ValueError('Choose a recorded session')
    bars=pd.DataFrame()
    if date:
        bars=pd.DataFrame(json.loads((folder/(date+'.json')).read_text()))
        for c in ['bar_start','bar_end','session_open','session_close']:bars[c]=pd.to_datetime(bars[c],utc=True)
        bars=bars[bars.bar_end<=now].sort_values('bar_start')
        if bars.bar_start.duplicated().any():raise ValueError('Duplicate recorded minutes')
        if not np.isfinite(bars[['open','high','low','close','volume']]).all().all():raise ValueError('Invalid recorded prices')
    selected=[r for r in rows if r.get('source')=='webull_official' and r.get('symbol','QQQ')==symbol and pd.Timestamp(r['last_input_timestamp']).tz_convert('America/New_York').strftime('%Y-%m-%d')==date]
    scored=[score(r,bars,now) for r in selected]
    groups=defaultdict(list)
    for r in scored:groups[r['settings']].append(r)
    daily=[]
    for settings,items in groups.items():
        valid=[r for r in items if r['prospective'] and r['status']=='complete']
        daily.append(dict(settings=settings,total=len(items),scored=len(valid),pending=sum(r['status']=='pending' for r in items),incomplete=sum(r['status']=='incomplete' for r in items),late_or_unknown=sum(not r['prospective'] for r in items),
            **{key:float(np.mean([r[key] for r in valid if r[key] is not None])) if any(r[key] is not None for r in valid) else None for key in ['close_error','baseline_error','high_error','low_error']},
            touch=summary([r for r in items if r['prospective']])))
    last=bars.iloc[-1].bar_end if len(bars) else None
    expected=pd.date_range(bars.iloc[0].session_open,min(now.floor('min'),bars.iloc[0].session_close),freq='min',inclusive='left') if len(bars) else []
    gaps=len(pd.DatetimeIndex(expected).difference(bars.bar_start)) if len(bars) else None
    status='no recordings' if last is None else 'market closed / historical' if now>=bars.iloc[0].session_close else 'recent candles' if (now-last).total_seconds()<=120 else 'stale — recorder may be stopped'
    result=dict(symbol=symbol,date=date,dates=dates,status=status,latest_candle=last.isoformat() if last is not None else None,
                latest_forecast=max((r['created_at'] for r in scored if r['created_at']),default=None),missing_minutes=gaps,daily=daily,rows=list(reversed(scored[-100:])),review='Exploratory monitored data; not untouched confirmation')
    # Derived review snapshots survive browser/server restarts. Original records stay immutable.
    destination=output/'forward_review';destination.mkdir(exist_ok=True)
    if date:
        target=destination/f'{symbol}-{date}.json';temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(result,allow_nan=False),encoding='utf-8');temp.replace(target)
    return result
