"""June tape resolution, unchanged barriers, conservative encounter grouping."""
import json
from collections import Counter
import numpy as np
import pandas as pd
import databento as db
from build_zone_response import ROOT,digest
from freeze_jev_sample import save_frozen
from level_probability_lab.zone_tape import resolve


def resolve_fast(trades,event,touch):
    """Trim only irrelevant timestamps; preserve tied timestamp groups."""
    t=trades[(trades.ts_recv>=pd.Timestamp(event['cutoff'])) & (trades.ts_recv<pd.Timestamp(touch)+pd.Timedelta(minutes=15))]
    level,risk=event['level'],event['risk']
    inside=t.price.between(level-.1*risk,level+.1*risk)
    gap=t.price<level-.1*risk if event['price']>level else t.price>level+.1*risk
    relevant=t[inside|gap]
    if relevant.empty:return dict(status='no_trade_in_zone',touch=None)
    first=relevant.ts_recv.min()
    t=t[t.ts_recv>=first]
    barrier=t[(t.ts_recv>first)&((t.price>=level+.5*risk)|(t.price<=level-.5*risk))]
    if len(barrier):t=t[t.ts_recv<=barrier.ts_recv.min()]
    return resolve(t,event,touch)


def main():
    folder=ROOT/'data/zone_response_v2'
    inputs={r['id']:r for r in json.loads((folder/'inputs.json').read_text())}
    outcomes=json.loads((folder/'outcomes.json').read_text())
    selected=[r for r in outcomes if 'touch' in r]
    # All touched records, not only ambiguous cases, receive the same tape check.
    raw=ROOT/'data/raw/XNAS_ITCH_81b52cd2b2a9.trades.dbn.zst'
    feature=ROOT/'data/trades_study/trade_features_may_june.parquet'
    audit=json.loads((feature.parent/'trade_feature_audit.json').read_text())
    if not audit['accepted'] or digest(raw)!=audit['raw_sha256'] or digest(feature)!=audit['features_sha256']:raise ValueError('Audit/hash mismatch')
    save_frozen(folder/'tape_manifest.json',dict(inputs_sha256=digest(folder/'inputs.json'),outcomes_sha256=digest(folder/'outcomes.json'),raw_sha256=digest(raw),code_sha256=digest(ROOT/'scripts/resolve_zone_tape_v2.py'),grouping='Same date and level family; overlapping [cutoff,touch+15m) windows form connected components; earliest cutoff represents each component; no outcome selection'))
    windows={}
    for r in selected:
        e=inputs[r['id']]; windows.setdefault(e['date'],[]).append((pd.Timestamp(e['cutoff']),pd.Timestamp(r['touch'])+pd.Timedelta(minutes=15)))
    parts=[]
    for chunk in db.DBNStore.from_file(raw).to_df(price_type='float',pretty_ts=True,count=250000):
        recv=chunk.index
        if recv.min()>=pd.Timestamp('2026-07-01',tz='UTC'):break
        mask=np.zeros(len(chunk),bool)
        for day,ws in windows.items():
            if recv.max()<min(a for a,b in ws) or recv.min()>=max(b for a,b in ws):continue
            for a,b in ws:mask|=(recv>=a)&(recv<b)
        if mask.any():parts.append(chunk.loc[mask].reset_index()[['ts_recv','ts_event','price','size','flags','symbol']])
    tape=pd.concat(parts,ignore_index=True).sort_values('ts_recv',kind='stable')
    tape['minute']=tape.ts_recv.dt.floor('min')
    features=pd.read_parquet(feature).set_index('bar_start')
    valid={}
    for m,g in tape.groupby('minute'):
        f=features.loc[m] if m in features.index else None
        valid[m]=bool(f is not None and f.feature_eligible and f.reconciled and (g.symbol=='QQQ').all() and ((g['flags'].astype(int)&12)==0).all() and np.isfinite(g[['price','size']]).all().all() and (g[['price','size']]>0).all().all() and np.allclose([g.price.iloc[0],g.price.max(),g.price.min(),g.price.iloc[-1],g['size'].sum(),len(g)],[f.open,f.high,f.low,f.close,f.volume,f.trade_count],rtol=0,atol=1e-7))
    days={d:g for d,g in tape.groupby(tape.ts_recv.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d'))}
    resolved=[]
    for r in selected:
        e=inputs[r['id']]; start=pd.Timestamp(e['cutoff']);end=pd.Timestamp(r['touch'])+pd.Timedelta(minutes=15)
        good=all(valid.get(m,False) for m in pd.date_range(start,end,freq='min',inclusive='left'))
        result=resolve_fast(days[e['date']],e,r['touch']) if good else dict(status='incomplete',reason='window reconciliation failed')
        resolved.append(dict(id=e['id'],date=e['date'],name=e['name'],cutoff=e['cutoff'],window_end=end.isoformat(),candle_status=r['status'],tape=result))
    save_frozen(folder/'tape_outcomes.json',resolved)
    groups=[]
    for key,rows in pd.DataFrame(resolved).groupby(['date','name']):
        active=None
        for r in sorted(rows.to_dict('records'),key=lambda x:(x['cutoff'],x['id'])):
            if active is None or r['cutoff']>=active['end']:
                active=dict(date=key[0],name=key[1],representative=r['id'],end=r['window_end'],members=[],status=r['tape']['status']);groups.append(active)
            active['members'].append(r['id']);active['end']=max(active['end'],r['window_end'])
    save_frozen(folder/'encounters.json',groups)
    rng=np.random.default_rng(42);summary={}
    all_dates=sorted({e['date'] for e in inputs.values()})
    for name in sorted({e['name'] for e in inputs.values()}):
        g=[x for x in groups if x['name']==name];counts=dict(Counter(x['status'] for x in g))
        daily=np.array([[sum(x['date']==d and x['status']==s for x in g) for s in ['rejection','continuation']] for d in all_dates])
        boot=daily[rng.integers(0,len(daily),(5000,len(daily)))].sum(axis=1);den=boot.sum(axis=1);rates=boot[den>0,0]/den[den>0]
        summary[name]=dict(encounters=len(g),counts=counts,resolved_rejection_fraction=float(daily[:,0].sum()/daily.sum()) if daily.sum() else None,descriptive_session_bootstrap_95=np.quantile(rates,[.025,.975]).tolist() if len(rates) else None)
    save_frozen(folder/'tape_summary.json',dict(touched_records=len(resolved),verified_minutes=sum(valid.values()),failed_minutes=sum(not v for v in valid.values()),by_level=summary))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

