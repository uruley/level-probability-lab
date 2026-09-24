"""Audit every pre-close tape minute in the eight incomplete representatives."""
import json
import numpy as np
import pandas as pd
import databento as db
from build_zone_response import ROOT,digest
from freeze_jev_sample import save_frozen
from level_probability_lab.calendar import session_schedule


def main():
    folder=ROOT/'data/zone_response_v2';out=ROOT/'data/sma200_matched_v1'
    selected=[r for r in json.loads((folder/'encounters.json').read_text()) if r['name']=='1m SMA 200' and r['status']=='incomplete']
    records={r['id']:r for r in json.loads((folder/'tape_outcomes.json').read_text())}
    schedule=session_schedule('2026-06-01','2026-06-30')
    windows=[(pd.Timestamp(records[g['representative']]['cutoff']),schedule.loc[pd.Timestamp(g['date'])].market_close) for g in selected]
    raw=ROOT/'data/raw/XNAS_ITCH_81b52cd2b2a9.trades.dbn.zst';feature=ROOT/'data/trades_study/trade_features_may_june.parquet'
    audit=json.loads((feature.parent/'trade_feature_audit.json').read_text())
    if not audit['accepted'] or digest(raw)!=audit['raw_sha256'] or digest(feature)!=audit['features_sha256']:raise ValueError('Hash mismatch')
    parts=[]
    for chunk in db.DBNStore.from_file(raw).to_df(price_type='float',pretty_ts=True,count=250000):
        recv=chunk.index
        if recv.min()>=max(b for a,b in windows):break
        mask=np.zeros(len(chunk),bool)
        for a,b in windows:
            if recv.max()>=a and recv.min()<b:mask|=(recv>=a)&(recv<b)
        if mask.any():parts.append(chunk.loc[mask].reset_index()[['ts_recv','price','size','flags','symbol']])
    tape=pd.concat(parts,ignore_index=True);groups={m:g for m,g in tape.groupby(tape.ts_recv.dt.floor('min'))};features=pd.read_parquet(feature).set_index('bar_start');results=[]
    for e,(a,b) in zip(selected,windows):
        failures=[];grid=pd.date_range(a,b,freq='min',inclusive='left')
        for m in grid:
            g=groups.get(m);f=features.loc[m] if m in features.index else None
            good=g is not None and f is not None and f.feature_eligible and f.reconciled
            if good:good=(g.symbol=='QQQ').all() and ((g['flags'].astype(int)&12)==0).all() and np.isfinite(g[['price','size']]).all().all() and (g[['price','size']]>0).all().all() and np.allclose([g.price.iloc[0],g.price.max(),g.price.min(),g.price.iloc[-1],g['size'].sum(),len(g)],[f.open,f.high,f.low,f.close,f.volume,f.trade_count],rtol=0,atol=1e-7)
            if not good:failures.append(m.isoformat())
        results.append(dict(id=e['representative'],preclose_minutes=len(grid),failed_minutes=failures,original_status='incomplete'))
    save_frozen(out/'preclose_tape_audit.json',dict(raw_sha256=digest(raw),features_sha256=digest(feature),events=results))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
