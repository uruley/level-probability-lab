"""Fixed matched June comparison and incomplete-window audit; offline only."""
import json, math
from collections import Counter
import pandas as pd
import numpy as np
import databento as db
from build_zone_response import ROOT,digest
from freeze_jev_sample import save_frozen
from resolve_zone_tape_v2 import resolve_fast
from level_probability_lab.calendar import session_schedule
from level_probability_lab.zone_response import observe


def match_cases(events, schedule):
    events=sorted(events,key=lambda e:e['cutoff'])
    pool=[e for e in events if e['level'] is not None and e['risk']>0 and pd.Timestamp(e['cutoff'])+pd.Timedelta(minutes=75)<=schedule.loc[pd.Timestamp(e['date'])].market_close]
    cases=[]; last={}
    for e in pool:
        t=pd.Timestamp(e['cutoff'])
        if e['date'] not in last or t>=last[e['date']]+pd.Timedelta(minutes=75):cases.append(e);last[e['date']]=t
    pairs=[];used=[]
    for case in cases:
        t=pd.Timestamp(case['cutoff']); d=(case['price']-case['level'])/case['risk'];options=[]
        for c in pool:
            ct=pd.Timestamp(c['cutoff']);delta=abs((ct.hour*60+ct.minute)-(t.hour*60+t.minute));ratio=c['risk']/case['risk']
            if c['date']==case['date'] or delta>15 or not .8<=ratio<=1.25:continue
            if any(day==c['date'] and abs((ct-old).total_seconds())<4500 for day,old in used):continue
            level=c['price']-d*c['risk']
            if abs(level-c['level'])/c['risk']<1:continue
            options.append((abs(math.log(ratio))+delta/15,c['cutoff'],c,level))
        if not options:pairs.append(dict(case=case,control=None));continue
        _,_,c,level=min(options,key=lambda x:(x[0],x[1]))
        used.append((c['date'],pd.Timestamp(c['cutoff'])))
        pairs.append(dict(case=case,control={**c,'id':case['id']+'|control|'+c['cutoff'],'name':'Matched placebo','actual_sma200':c['level'],'level':level}))
    return pairs


def main():
    folder=ROOT/'data/zone_response_v2';out=ROOT/'data/sma200_matched_v1';out.mkdir(exist_ok=True)
    allinputs=json.loads((folder/'inputs.json').read_text());events=[e for e in allinputs if e['name']=='1m SMA 200']
    schedule=session_schedule('2026-06-01','2026-06-30')
    feature=ROOT/'data/trades_study/trade_features_may_june.parquet';audit=json.loads((feature.parent/'trade_feature_audit.json').read_text())
    raw=ROOT/'data/raw/XNAS_ITCH_81b52cd2b2a9.trades.dbn.zst'
    if not audit['accepted'] or digest(feature)!=audit['features_sha256'] or digest(raw)!=audit['raw_sha256']:raise ValueError('Audit mismatch')
    bars=pd.read_parquet(feature);idx=bars.set_index('bar_start')
    groups=json.loads((folder/'encounters.json').read_text());old={r['id']:r for r in json.loads((folder/'tape_outcomes.json').read_text())}
    missing=[]
    for g in groups:
        if g['name']!='1m SMA 200' or g['status']!='incomplete':continue
        r=old[g['representative']];grid=pd.date_range(r['cutoff'],r['window_end'],freq='min',inclusive='left');closing=schedule.loc[pd.Timestamp(r['date'])].market_close
        absent=grid.difference(idx.index);before=idx.reindex(grid[grid<closing])
        missing.append(dict(id=r['id'],missing_minutes=[t.isoformat() for t in absent],all_missing_after_close=bool((absent>=closing).all()),preclose_features_valid=bool(before.feature_eligible.fillna(False).all() and before.reconciled.fillna(False).all())))
    save_frozen(out/'incomplete_audit.json',missing)
    pairs=match_cases(events,schedule);save_frozen(out/'pairs.json',pairs)
    save_frozen(out/'manifest.json',dict(protocol_sha256=digest(ROOT/'docs/SMA200_MATCHED_V1.md'),inputs_sha256=digest(folder/'inputs.json'),raw_sha256=digest(raw),features_sha256=digest(feature),code_sha256=digest(ROOT/'scripts/sma200_matched_v1.py')))
    selected=[e for p in pairs if p['control'] is not None for e in [p['case'],p['control']]]
    days={d:g for d,g in bars.groupby(bars.bar_start.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d'))}
    candle={e['id']:observe(days[e['date']],e['cutoff'],e['level'],e['price'],e['risk']) for e in selected}
    windows=[(pd.Timestamp(e['cutoff']),pd.Timestamp(candle[e['id']]['touch'])+pd.Timedelta(minutes=15)) for e in selected if 'touch' in candle[e['id']]]
    print(f'{len(pairs)} cases; {len(selected)//2} pairs; {len(windows)} touched windows',flush=True)
    parts=[]
    for chunk in db.DBNStore.from_file(raw).to_df(price_type='float',pretty_ts=True,count=250000):
        recv=chunk.index
        if recv.min()>=pd.Timestamp('2026-07-01',tz='UTC'):break
        mask=np.zeros(len(chunk),bool)
        for a,b in windows:
            if recv.max()>=a and recv.min()<b:mask|=(recv>=a)&(recv<b)
        if mask.any():parts.append(chunk.loc[mask].reset_index()[['ts_recv','ts_event','price','size','flags','symbol']])
    tape=pd.concat(parts,ignore_index=True).sort_values('ts_recv',kind='stable') if parts else pd.DataFrame()
    valid={};tdays={}
    if len(tape):
        for m,g in tape.groupby(tape.ts_recv.dt.floor('min')):
            f=idx.loc[m] if m in idx.index else None
            valid[m]=bool(f is not None and f.feature_eligible and f.reconciled and (g.symbol=='QQQ').all() and ((g['flags'].astype(int)&12)==0).all() and np.isfinite(g[['price','size']]).all().all() and (g[['price','size']]>0).all().all() and np.allclose([g.price.iloc[0],g.price.max(),g.price.min(),g.price.iloc[-1],g['size'].sum(),len(g)],[f.open,f.high,f.low,f.close,f.volume,f.trade_count],rtol=0,atol=1e-7))
        tdays={d:g for d,g in tape.groupby(tape.ts_recv.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d'))}
    results={}
    for e in selected:
        r=candle[e['id']];result=r
        if 'touch' in r:
            grid=pd.date_range(e['cutoff'],pd.Timestamp(r['touch'])+pd.Timedelta(minutes=15),freq='min',inclusive='left')
            result=resolve_fast(tdays[e['date']],e,r['touch']) if all(valid.get(t,False) for t in grid) else dict(status='incomplete',reason='tape audit failed')
        results[e['id']]=dict(candle=r,final=result)
    save_frozen(out/'outcomes.json',results)
    matched=[p for p in pairs if p['control'] is not None];counts={arm:dict(Counter(results[p[arm]['id']]['final']['status'] for p in matched)) for arm in ['case','control']}
    differences=[int(results[p['case']['id']]['final']['status']=='rejection')-int(results[p['control']['id']]['final']['status']=='rejection') for p in matched]
    report=dict(selected_cases=len(pairs),matched_pairs=len(matched),unmatched=len(pairs)-len(matched),counts=counts,paired_rejection_frequency_difference=float(np.mean(differences)) if differences else None,paired_difference_counts=dict(Counter(differences)),inference='Descriptive development only; shared sessions and prior exposure; no calibrated probability or edge established')
    save_frozen(out/'summary.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
