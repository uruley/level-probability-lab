"""Independent audit of August ledgers and actual first-touch outcomes."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, load_day

OUT=ROOT/'data/location_evaluation_v3_august'


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    cfg=json.loads((OUT/'frozen_config.json').read_text())
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert digest(OUT/'frozen_config.json')==manifest['config_sha256']
    for name,sha in cfg['code'].items(): assert digest(ROOT/name)==sha
    for name,sha in manifest['outputs'].items(): assert digest(OUT/name)==sha
    inputs=json.loads((OUT/'inputs_manifest.json').read_text())
    for item in inputs['files']: assert digest(ROOT/item['path'])==item['sha256']
    frame=pd.read_csv(OUT/'outcomes.csv'); features=pd.read_csv(OUT/'classifications.csv')
    assert len(frame)==6804 and not frame.duplicated(['forecast_id','horizon','ratio']).any()
    assert set(frame.month)=={'2026-08'}
    assert frame.groupby('date').forecast_id.nunique().eq(54).all()
    assert frame.groupby('forecast_id').size().eq(6).all()
    assert frame.groupby('date').ngroups==21
    ids=set(); origins=[]
    with (OUT/'prediction_contexts.jsonl').open(encoding='utf-8') as ledger:
        for line in ledger:
            row=json.loads(line); cid=row.pop('context_id'); ids.add(cid)
            assert hashlib.sha256(json.dumps(row,sort_keys=True,allow_nan=False).encode()).hexdigest()==cid
            origins.append(dict(date=row['date'],origin=row['origin']))
            cutoff=pd.Timestamp(row['origin'])+pd.Timedelta(minutes=1)
            assert pd.Timestamp(row['context']['as_of'])==cutoff
            assert all(v['available_at'] is None or pd.Timestamp(v['available_at'])<=cutoff for v in row['context']['levels'])
    assert origins==cfg['origins'] and len(ids)==1134 and ids==set(frame.context_id)==set(features.context_id)
    checked=0
    for day,sub in frame.groupby('date'):
        bars=load_day(ROOT/'data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet',day)
        # Vectorized independent first-index calculation for every setup and control.
        for row in sub.itertuples():
            cutoff=pd.Timestamp(row.origin)+pd.Timedelta(minutes=1)
            deadline=min(cutoff+pd.Timedelta(minutes=row.horizon),bars.iloc[0].session_close)
            assert pd.Timestamp(row.deadline)==deadline
            future=bars.loc[(bars.bar_start>=cutoff)&(bars.bar_end<=deadline)]
            assert len(future)==row.available_minutes
            assert list(future.bar_start)==list(pd.date_range(cutoff,deadline,freq='min',inclusive='left'))
            for engine in ['kronos','always_up','always_down','momentum5']:
                d=getattr(row,engine+'_direction')
                if not d:
                    assert getattr(row,engine+'_status')=='no_setup'; continue
                target=getattr(row,engine+'_target'); stop=getattr(row,engine+'_stop')
                assert np.isclose(target,row.reference+d*row.ratio*row.risk)
                assert np.isclose(stop,row.reference-d*row.risk)
                a=np.flatnonzero(future.high.to_numpy()>=target if d==1 else future.low.to_numpy()<=target)
                b=np.flatnonzero(future.low.to_numpy()<=stop if d==1 else future.high.to_numpy()>=stop)
                first_a=int(a[0])+1 if len(a) else float('inf')
                first_b=int(b[0])+1 if len(b) else float('inf')
                expected=('expired' if row.horizon==60 else 'neither') if first_a==first_b==float('inf') else 'ambiguous' if first_a==first_b else 'target_first' if first_a<first_b else 'stop_first'
                assert getattr(row,engine+'_status')=='complete' and getattr(row,engine+'_outcome')==expected
                assert getattr(row,engine+'_minutes')==min(first_a,first_b,len(future))
                checked+=1
        print(day+': independent touch audit passed',flush=True)
    report=json.loads((OUT/'report.json').read_text())
    for r in report['results']:
        sub=frame.loc[(frame.horizon==r['horizon'])&(frame.ratio==r['ratio'])&(frame[r['family']+'_band']==r['band'])]
        valid=sub.loc[sub.kronos_status=='complete']
        assert len(sub)==r['origins'] and len(valid)==r['complete']
        assert valid.kronos_outcome.value_counts().to_dict()==r['counts']
        paired=sub.loc[(sub.kronos_status=='complete')&(sub.always_up_status=='complete')&(sub.always_down_status=='complete')]
        if len(paired):
            coin=.5*((paired.always_up_outcome=='target_first').mean()+(paired.always_down_outcome=='target_first').mean())
            assert abs(coin-r['coin_rate'])<1e-12
            assert abs((paired.kronos_outcome=='target_first').mean()-coin-r['excess_vs_coin']['value'])<1e-12
    result=dict(passed=True,contexts=1134,forecast_hashes=1134,outcome_rows=6804,
                independent_touch_checks=checked,summary_rows=len(report['results']),code_and_artifact_hashes=True)
    path=OUT/'independent_verification.json'
    with path.open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)


if __name__=='__main__': main()
