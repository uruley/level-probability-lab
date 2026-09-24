"""Read existing DBN only, filtering four May event windows; no network."""
import hashlib
import json
from pathlib import Path
import databento as db
import numpy as np
import pandas as pd
from level_probability_lab.zone_tape import resolve
from freeze_jev_sample import save_frozen

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'data/zone_response_v1'
    inputs={r['id']:r for r in json.loads((folder/'inputs.json').read_text())}
    selected=[r for r in json.loads((folder/'outcomes.json').read_text()) if r['status']=='ambiguous']
    if len(selected)!=4:raise ValueError('Expected four fixed ambiguous events')
    raw=ROOT/'data/raw/XNAS_ITCH_81b52cd2b2a9.trades.dbn.zst'
    audit=json.loads((ROOT/'data/trades_study/trade_feature_audit.json').read_text())
    with raw.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=audit['raw_sha256'] or not audit['accepted']:raise ValueError('Raw audit mismatch')
    windows=[(pd.Timestamp(inputs[r['id']]['cutoff']),pd.Timestamp(r['touch'])+pd.Timedelta(minutes=15)) for r in selected]
    parts=[]
    for chunk in db.DBNStore.from_file(raw).to_df(price_type='float',pretty_ts=True,count=250000):
        recv=chunk.index if chunk.index.name=='ts_recv' else pd.DatetimeIndex(chunk.ts_recv)
        if recv.min()>=max(b for a,b in windows):break
        mask=np.zeros(len(chunk),dtype=bool)
        for a,b in windows:mask|=(recv>=a)&(recv<b)
        if mask.any():
            part=chunk.loc[mask].copy()
            if part.index.name=='ts_recv':part=part.reset_index()
            parts.append(part[['ts_recv','ts_event','price','size','flags','symbol','sequence']])
    tape=pd.concat(parts,ignore_index=True)
    if not (tape.symbol=='QQQ').all() or ((tape['flags'].astype(int)&12)!=0).any() or not np.isfinite(tape[['price','size']]).all().all() or (tape[['price','size']]<=0).any().any():raise ValueError('Tape quality failure')
    features=pd.read_parquet(ROOT/'data/trades_study/trade_features_may_june.parquet').set_index('bar_start')
    outcomes=[]
    for original,(start,end) in zip(selected,windows):
        event=inputs[original['id']]; trades=tape[(tape.ts_recv>=start)&(tape.ts_recv<end)].copy()
        trades['minute']=trades.ts_recv.dt.floor('min')
        groups={m:g for m,g in trades.groupby('minute')}
        for minute in pd.date_range(start,end,freq='min',inclusive='left'):
            if minute not in groups or minute not in features.index:raise ValueError('Coverage gap')
            g=groups[minute];f=features.loc[minute]
            observed=[g.price.iloc[0],g.price.max(),g.price.min(),g.price.iloc[-1],g['size'].sum(),len(g)]
            if not f.feature_eligible or not f.reconciled or not np.allclose(observed,[f.open,f.high,f.low,f.close,f.volume,f.trade_count],rtol=0,atol=1e-7):raise ValueError('Minute reconciliation failure')
        result=resolve(trades,event,original['touch'])
        # Report event-order inversion rather than silently substituting clocks.
        inversions=int((trades.ts_event.diff().dropna()<pd.Timedelta(0)).sum())
        outcomes.append(dict(id=original['id'],candle_status=original['status'],tape=result,
            receive_order_event_time_inversions=inversions,verified_minutes=len(groups),records=len(trades)))
    result=dict(raw_sha256=digest,clock='ts_recv; equal timestamp ordering remains ambiguous',
        scope='Nasdaq-only prints, not consolidated orders/fills',outcomes=outcomes,
        inputs_sha256=hashlib.sha256((folder/'inputs.json').read_bytes()).hexdigest(),
        original_outcomes_sha256=hashlib.sha256((folder/'outcomes.json').read_bytes()).hexdigest())
    save_frozen(folder/'tape_outcomes.json',result)
    tape.to_parquet(folder/'selected_tape.parquet',index=False)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
