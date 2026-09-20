"""Independent artifact/touch-order audit; no fitting or inference."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from level_probability_lab.lab import ROOT, load_day


def main():
    out=ROOT/'data/location_evaluation_v1';df=pd.read_csv(out/'outcomes.csv')
    assert len(df)==2214*6 and not df.duplicated(['forecast_id','horizon','ratio']).any()
    assert set(df.month)=={'2026-05','2026-06'}
    context_count=0;identities=set()
    with (out/'prediction_contexts.jsonl').open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);identity=row.pop('context_id')
            assert hashlib.sha256(json.dumps(row,sort_keys=True,allow_nan=False).encode()).hexdigest()==identity
            identities.add(identity);context_count+=1
            cutoff=pd.Timestamp(row['context']['as_of'])
            assert cutoff==pd.Timestamp(row['origin'])+pd.Timedelta(minutes=1)
            assert all(v['available_at'] is None or pd.Timestamp(v['available_at'])<=cutoff for v in row['context']['levels'])
    assert context_count==2214 and identities==set(df.context_id)
    checked=0
    source=ROOT/'data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet'
    for date,session in df.groupby('date'):
        bars=load_day(source,date)
        # Late-session origin tests session-close expiry, independently of replay observer.
        subset=session.loc[session.origin==session.origin.max()]
        for row in subset.itertuples():
            cutoff=pd.Timestamp(row.origin)+pd.Timedelta(minutes=1)
            future=bars.loc[(bars.bar_start>=cutoff)&(bars.bar_end<=pd.Timestamp(row.deadline))]
            assert len(future)==row.available_minutes
            for engine in ['kronos','always_up','always_down','momentum5']:
                direction=getattr(row,engine+'_direction')
                if not direction:
                    assert getattr(row,engine+'_status')=='no_setup';continue
                target=getattr(row,engine+'_target');stop=getattr(row,engine+'_stop')
                target_indices=future.index[future.high>=target if direction==1 else future.low<=target]
                stop_indices=future.index[future.low<=stop if direction==1 else future.high>=stop]
                a=target_indices.min() if len(target_indices) else float('inf')
                b=stop_indices.min() if len(stop_indices) else float('inf')
                expected=('expired' if row.horizon==60 else 'neither') if a==b==float('inf') else 'ambiguous' if a==b else 'target_first' if a<b else 'stop_first'
                assert getattr(row,engine+'_outcome')==expected
                checked+=1
    report=json.loads((out/'report.json').read_text())
    for r in report['results']:
        assert sum(r['counts'].values())==r['complete']
        assert r['complete']+r['missing']+r['no_setup']==r['origins']
        if r['complete']:assert abs(r['target_rate']['value']-r['counts'].get('target_first',0)/r['complete'])<1e-12
    result=dict(context_hashes_verified=context_count,late_session_baseline_outcomes_verified=checked,sessions=41,summary_denominators_verified=len(report['results']),passed=True)
    (out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
