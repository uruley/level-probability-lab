"""Official QQQ candle polling and local recordings; no account/order APIs."""
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import numpy as np
import pandas as pd
from .calendar import session_schedule

SCANNER=Path(r'C:\Users\ruley\WebullTradingScanner')


def normalize(records,minutes,now):
    if not records: raise ValueError('Webull returned no candles.')
    frame=pd.DataFrame(records).rename(columns={'timestamp':'bar_start'})
    frame['bar_start']=pd.to_datetime(frame.bar_start,utc=True,errors='raise')
    fields=['open','high','low','close','volume']
    frame[fields]=frame[fields].apply(pd.to_numeric,errors='raise')
    if frame.bar_start.duplicated().any() or not np.isfinite(frame[fields].to_numpy(float)).all():
        raise ValueError('Webull returned duplicate or non-finite candles.')
    if (frame[fields]<=0).any().any() or (frame.high<frame[['open','low','close']].max(axis=1)).any() or (frame.low>frame[['open','close']].min(axis=1)).any():
        raise ValueError('Webull returned invalid OHLC or volume.')
    frame['bar_end']=frame.bar_start+pd.Timedelta(minutes=minutes)
    frame=frame.loc[frame.bar_end<=now-pd.Timedelta(seconds=5)].sort_values('bar_start')
    if frame.empty: raise ValueError('Waiting for a completed Webull candle.')
    schedule=session_schedule(str(frame.bar_start.min().date()),str(frame.bar_start.max().date()))
    parts=[]
    for r in schedule.itertuples():
        part=frame.loc[(frame.bar_start>=r.market_open)&(frame.bar_end<=r.market_close)].copy()
        if not part.empty:
            if ((part.bar_start-r.market_open).dt.total_seconds()%(minutes*60)!=0).any(): raise ValueError('Unexpected Webull candle alignment.')
            part['session_open']=r.market_open;part['session_close']=r.market_close
            parts.append(part)
    if not parts: raise ValueError('No completed regular-session candles returned.')
    return pd.concat(parts,ignore_index=True)


def feed_status(bars,now,error=None):
    if error:return dict(ready=False,status='error',message=error)
    today=now.tz_convert('America/New_York').strftime('%Y-%m-%d')
    schedule=session_schedule(today,today)
    if schedule.empty or now<schedule.iloc[0].market_open or now>=schedule.iloc[0].market_close:
        return dict(ready=False,status='market_closed',message='Regular market is closed. Showing the latest recorded session; no live forecasts.')
    if bars.iloc[-1].bar_end<now-pd.Timedelta(seconds=95):
        return dict(ready=False,status='stale',message='Waiting for current completed candles. Stale data cannot trigger forecasts.')
    return dict(ready=True,status='live',message='Official Webull · completed candles · checking after each minute closes.')


class Feed:
    def __init__(self,root,output,symbol="QQQ"):
        if symbol not in ("QQQ","TSLA","NVDA"):raise ValueError("Unsupported symbol")
        self.symbol=symbol
        self.root=Path(root);self.output=Path(output)/'webull';self.lock=threading.RLock()
        if symbol!='QQQ':self.output=self.output/symbol
        self.frames={};self.last_poll=0.;self.sid=None;self.error=None

    def fetch(self):
        with self.lock:
            if time.monotonic()-self.last_poll<4 and self.frames and not self.error:return self.frames
            request=dict(action='fetch',symbol=self.symbol,warmup=not self.frames or bool(self.error) or time.monotonic()-self.last_poll>3600)
            try:
                result=subprocess.run([str(SCANNER/'.venv/Scripts/python.exe'),str(self.root/'scripts/webull_data_worker.py')],
                    input=json.dumps(request)+'\n',capture_output=True,text=True,timeout=85,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),cwd=self.root)
                data=json.loads(result.stdout)
                if not data.get('ok'):raise ValueError(data.get('error','Webull data request failed.'))
                if data.get('provider')!='webull_official' or data.get('symbol')!=self.symbol:raise ValueError('Unexpected Webull data source.')
                now=pd.Timestamp.now(tz='UTC'); updated=dict(self.frames)
                for key,records in data['frames'].items():
                    incoming=normalize(records,1 if key=='M1' else 5,now)
                    old=updated.get(key,pd.DataFrame())
                    updated[key]=pd.concat([old,incoming],ignore_index=True).drop_duplicates('bar_start',keep='last').sort_values('bar_start').reset_index(drop=True)
                # Derive new M5 buckets from minute bars; never fill a missing minute.
                from .hour_forecast import aggregate
                m1=updated['M1'];schedule=session_schedule(str(m1.bar_start.min().date()),str(m1.bar_start.max().date()))
                m5=aggregate(m1,schedule)
                m5=m5.loc[(m5.bar_end<=now-pd.Timedelta(seconds=5))&m5.close.notna()]
                updated['M5']=pd.concat([updated.get('M5',pd.DataFrame()),m5],ignore_index=True).drop_duplicates('bar_start',keep='last').sort_values('bar_start').reset_index(drop=True)
                self.frames=updated;self.error=None;self.last_poll=time.monotonic()
                self.save(data,now)
                return self.frames
            except Exception as exc:
                self.error=str(exc) if isinstance(exc,ValueError) and not isinstance(exc,json.JSONDecodeError) else 'Webull connection failed or timed out. Reconnect to retry.'
                raise ValueError(self.error) from None

    def save(self,raw,now):
        self.output.mkdir(parents=True,exist_ok=True)
        payload=json.dumps(dict(received_at=now.isoformat(),**raw),sort_keys=True,allow_nan=False)
        snapshots=self.output/'snapshots';snapshots.mkdir(exist_ok=True)
        path=snapshots/(hashlib.sha256(payload.encode()).hexdigest()+'.json')
        if not path.exists():path.write_text(payload,encoding='utf-8')
        for day,frame in self.frames['M1'].groupby(self.frames['M1'].bar_start.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')):
            # The current recording is replaceable; received snapshots/forecasts are immutable.
            target=self.output/(day+'.json');temp=target.with_suffix('.tmp')
            temp.write_text(frame.to_json(orient='records',date_format='iso'),encoding='utf-8');temp.replace(target)
        target=self.output/'five_minute.json';temp=target.with_suffix('.tmp')
        temp.write_text(self.frames['M5'].to_json(orient='records',date_format='iso'),encoding='utf-8');temp.replace(target)

    def dates(self):return sorted(p.stem for p in self.output.glob('????-??-??.json'))

    def recorded(self,date):
        if date not in self.dates():raise ValueError('No Webull recording for this date.')
        frame=pd.DataFrame(json.loads((self.output/(date+'.json')).read_text()))
        for col in ['bar_start','bar_end','session_open','session_close']:frame[col]=pd.to_datetime(frame[col],utc=True)
        return frame

    def hour_history(self):
        if 'M5' in self.frames:frame=self.frames['M5'].copy()
        else:
            path=self.output/'five_minute.json'
            if not path.exists():raise ValueError('No recorded Webull five-minute history.')
            frame=pd.DataFrame(json.loads(path.read_text()))
            for col in ['bar_start','bar_end']:frame[col]=pd.to_datetime(frame[col],utc=True)
        schedule=session_schedule(str(frame.bar_start.min().date()),str(frame.bar_start.max().date()))
        grid=[]
        for r in schedule.itertuples():grid.extend(pd.date_range(r.market_open,r.market_close,freq='5min',inclusive='left'))
        grid=[t for t in grid if frame.bar_start.min()<=t<=frame.bar_start.max()]
        frame=frame.set_index('bar_start').reindex(pd.DatetimeIndex(grid,name='bar_start')).reset_index()
        frame['bar_end']=frame.bar_start+pd.Timedelta(minutes=5)
        return frame
