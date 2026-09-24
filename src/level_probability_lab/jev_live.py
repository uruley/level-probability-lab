"""Opt-in QQQ observer. No network on status reads; durable daily reservations."""
import hashlib
import json
import threading
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import dotenv_values
from .jev_companion import request_real

RATE = .042 / 1_000_000
RESERVE = 65536 * RATE
CAP = .25

class LiveObserver:
    def __init__(self, root, output):
        self.root=Path(root); self.output=Path(output)/'jev_live'
        self.enabled=set(); self.lock=threading.RLock(); self.busy=False

    def toggle(self, session, enabled):
        if session.mode!='live' or session.symbol!='QQQ':
            raise ValueError('Jev observer currently supports live QQQ only')
        with self.lock:
            if enabled:self.enabled.add(session.date)
            else:self.enabled.discard(session.date)

    def rows(self, date):
        directory=self.output/date
        return sorted(directory.glob('*/record.json'))

    def submit(self, session, forecast):
        with self.lock:
            if session.mode!='live' or session.symbol!='QQQ' or session.date not in self.enabled or self.busy:return
            cutoff=pd.Timestamp(forecast['last_input_timestamp'])+pd.Timedelta(minutes=1)
            now=pd.Timestamp.now(tz='UTC')
            if not 0 <= (now-cutoff).total_seconds() < 60:return
            folder=self.output/session.date/cutoff.strftime('%H%M')
            if (folder/'record.json').exists():return
            if (len(self.rows(session.date))+1)*RESERVE>CAP:
                self.enabled.discard(session.date);return
            paths=np.asarray(forecast['sampled_paths'],float)
            if paths.ndim!=3 or paths.shape[1:]!=(5,4) or not np.isfinite(paths).all():return
            price=float(forecast['input_window'][-1]['close'])
            ret=(paths[:,:,3]/price-1)*10000
            kronos=dict(bull=float((ret[:,-1]>10).mean()),neutral=float((abs(ret[:,-1])<=10).mean()),bear=float((ret[:,-1]<-10).mean()))
            ctx=forecast.get('market_context',{})
            levels=[{k:v.get(k) for k in ('name','timeframe','value','available_at','distance_r')} for v in ctx.get('levels',[])
                if v.get('value') is not None and v.get('available_at') and pd.Timestamp(v['available_at'])<=cutoff]
            package=dict(schema_version='jev_live_v1',symbol='QQQ',cutoff=cutoff.isoformat(),origin_close=price,
                horizon_minutes=5,close_return_bp_quantiles=np.quantile(ret,[.1,.5,.9],axis=0).tolist(),
                kronos_scores=kronos,market_context=dict(levels=levels,status='partial' if levels else 'unavailable'))
            record=dict(forecast_id=forecast['forecast_id'],cutoff=cutoff.isoformat(),price=price,
                targets=forecast['target_timestamps'],kronos=kronos,package=package,
                reserved_usd=RESERVE,status='pending',outcome='pending')
            folder.mkdir(parents=True,exist_ok=True)
            with (folder/'record.json').open('x') as f:json.dump(record,f)
            self.busy=True
            threading.Thread(target=self._work,args=(folder,record),daemon=True).start()

    def _work(self, folder, record):
        try:
            key=dotenv_values(self.root/'.env').get('TYPESAFE_API_KEY')
            result=request_real(record['package'],api_key=key,model='jev-1.13.0',allow_network=True,cache_dir=folder/'api')
            record.update(status='ready',result=result,estimated_usd=result['usage']['input_tokens']*RATE)
        except Exception:
            record['status']='unavailable; request not retried; charge uncertain'
        finally:
            with self.lock:
                # Status/outcome polling cannot overwrite an in-flight update.
                record.update({k:v for k,v in json.loads((folder/'record.json').read_text()).items() if k in ('outcome','actual_close')})
                self.save(folder/'record.json',record);self.busy=False

    @staticmethod
    def save(path, value):
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value));tmp.replace(path)

    def status(self, session):
        with self.lock:
            rows=[]
            if session.symbol!='QQQ':
                return dict(enabled=False,supported=False,cap_usd=CAP,reserved_usd=0,estimated_usd=0,requests=0,busy=False,rows=[])
            bars=session.bars.iloc[:session.cursor+1]
            for path in self.rows(session.date):
                r=json.loads(path.read_text());targets=pd.to_datetime(r['targets'],utc=True)
                if r['outcome']=='pending' and len(bars) and bars.iloc[-1].bar_end>=targets[-1]+pd.Timedelta(minutes=1):
                    matched=bars.loc[bars.bar_start.isin(targets)]
                    if len(matched)!=5 or matched.bar_start.nunique()!=5:r['outcome']='incomplete'
                    else:
                        close=float(matched.sort_values('bar_start').iloc[-1].close);ret=close/r['price']-1
                        r.update(actual_close=close,outcome='bull' if ret>.001 else 'bear' if ret<-.001 else 'neutral')
                    self.save(path,r)
                rows.append(r)
            return dict(enabled=session.date in self.enabled,supported=session.mode=='live' and session.symbol=='QQQ',
                cap_usd=CAP,reserved_usd=len(rows)*RESERVE,estimated_usd=sum(r.get('estimated_usd',0) for r in rows),
                requests=len(rows),busy=self.busy,rows=rows[-30:])
