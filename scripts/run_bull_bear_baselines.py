"""Run from repository root: python scripts/run_bull_bear_baselines.py."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.lab import load_day
from level_probability_lab.calendar import session_schedule
from level_probability_lab.bull_bear_truth import snapshot,score,canonical
from level_probability_lab.bull_bear_baselines import label,distribution,summarize,CLASSES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/bull_bear_baselines_v1'
SOURCE=ROOT/'data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet'
ENGINES=('historical-analogue','kronos-small','kronos-mini')


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def truth(day,t):
    target=day.loc[(day.bar_start>=t)&(day.bar_start<=t+pd.Timedelta(minutes=5))]
    records=[]
    for r in target.to_dict('records'):
        r.update(symbol='QQQ',source_id=SOURCE.name+'|'+r['bar_start'].isoformat(),available_at=r['bar_end'])
        records.append(r)
    origin=t+pd.Timedelta(minutes=1)
    f=snapshot(records,origin,origin,experiment_id='bull-bear-baselines-v1',source=SOURCE.name,price_policy='vendor prices, no adjustment applied',availability_policy='assumed bar-end; corrections unavailable',code_version='truth-v1')
    o=score(f,records,origin+pd.Timedelta(minutes=5))
    if o['status']!='complete':raise ValueError(o['reasons'])
    return f,o


def main():
    manifest={str(SOURCE.relative_to(ROOT)):sha(SOURCE)}
    config=ROOT/'data/location_evaluation_v3_august/frozen_config.json'
    frozen=json.loads(config.read_text());assert manifest[str(SOURCE.relative_to(ROOT))]==frozen['source_sha256']
    train=[];excluded=[]
    for date in session_schedule('2026-05-01','2026-05-31').index:
        day=load_day(SOURCE,str(date.date()))
        opening=day.iloc[0].session_open;closing=day.iloc[0].session_close
        for end in pd.date_range(opening+pd.Timedelta(minutes=120),closing-pd.Timedelta(minutes=5),freq='5min'):
            t=end-pd.Timedelta(minutes=1)
            window=day.loc[(day.bar_start>=t-pd.Timedelta(minutes=119))&(day.bar_start<=t)]
            if len(window)!=120:excluded.append(dict(phase='train',origin=t.isoformat(),reason='missing lookback'));continue
            f,o=truth(day,t);train.append(dict(origin=f['origin_utc'],label=o['label']))
    freq=(np.bincount([CLASSES.index(r['label']) for r in train],minlength=3)/len(train)).tolist()
    rows=[];coverage=[]
    base_dir=ROOT/'data/location_evaluation_v3_august/forecasts/base'
    basefiles=sorted(base_dir.glob('202608*.json'))
    dates=sorted({json.loads(p.read_text())['date'] for p in basefiles})
    for date in dates:
        day=load_day(SOURCE,date);by=day.set_index('bar_start',drop=False)
        saved={}
        for engine in ENGINES:
            path=ROOT/'data/ghost_candles/eval'/engine/date/'forecasts.jsonl';manifest[str(path.relative_to(ROOT))]=sha(path)
            records=[json.loads(line) for line in path.read_text().splitlines()]
            saved[engine]={r['last_input_timestamp']:r for r in records}
            if len(saved[engine])!=len(records):raise ValueError('Duplicate origins')
        base={}
        for path in basefiles:
            if not path.name.startswith(date.replace('-','')):continue
            r=json.loads(path.read_text());base[r['origin']]=r;manifest[str(path.relative_to(ROOT))]=sha(path)
        shared=set(base).intersection(*(set(v) for v in saved.values()))
        coverage.append(dict(date=date,base=len(base),matched=len(shared),**{k:len(v) for k,v in saved.items()}))
        for key in sorted(shared):
            t=pd.Timestamp(key);b=base[key];window=by.loc[t-pd.Timedelta(minutes=119):t].reset_index(drop=True)
            fields=['bar_start','open','high','low','close','volume']
            assert len(window)==120
            assert hashlib.sha256(window[fields].to_csv(index=False).encode()).hexdigest()==b['input_sha256']
            f,o=truth(day,t);p0=float(f['origin_close']);targets=o['expected_starts']
            assert list(pd.to_datetime(b['targets'],utc=True))==list(pd.to_datetime(targets,utc=True))
            probabilities={'kronos-base':distribution(b['sampled_ohlc'],p0),'persistence':[0.,1.,0.],'may-frequency':freq}
            ids={'kronos-base':b['input_sha256']};versions={'kronos-base':frozen['base_revision']}
            for engine in ENGINES:
                r=saved[engine][key];w=pd.DataFrame(r['input_window']);w.bar_start=pd.to_datetime(w.bar_start,utc=True)
                assert list(w.bar_start)==list(window.bar_start)
                assert np.allclose(w[fields[1:]].to_numpy(float),window[fields[1:]].to_numpy(float),rtol=0,atol=1e-8)
                assert list(pd.to_datetime(r['target_timestamps'],utc=True))==list(pd.to_datetime(targets,utc=True))
                if engine=='historical-analogue':
                    ends=r['analogue_meta']['analogue_horizon_last_starts']
                    assert all(pd.Timestamp(x)+pd.Timedelta(minutes=1)<pd.Timestamp(f['origin_utc']) for x in ends)
                probabilities[engine]=distribution(r['sampled_paths'],p0);ids[engine]=r['forecast_id'];versions[engine]=r['model_revision']
            rows.append(dict(date=date,snapshot=f,outcome=o,raw_probabilities=probabilities,engine_ids=ids,engine_versions=versions))
        print(date,len(shared),flush=True)
    y=[CLASSES.index(r['outcome']['label']) for r in rows];sessions=[r['date'] for r in rows]
    report=dict(classes=CLASSES,train_n=len(train),train_frequency=freq,n=len(rows),sessions=len(set(sessions)),prevalence=(np.bincount(y,minlength=3)/len(y)).tolist(),coverage=coverage,excluded=excluded,engines={e:summarize(y,[r['raw_probabilities'][e] for r in rows],sessions,freq) for e in rows[0]['raw_probabilities']},status='RAW EXPERIMENTAL; previously inspected August development')
    for path in [config,Path(__file__),ROOT/'docs/BULL_BEAR_BASELINES_V1.md',ROOT/'src/level_probability_lab/bull_bear_truth.py',ROOT/'src/level_probability_lab/bull_bear_baselines.py']:manifest[str(path.relative_to(ROOT))]=sha(path)
    OUT.mkdir(exist_ok=True)
    outputs={'report.json':canonical(report),'manifest.json':canonical(manifest),'train_labels.json':canonical(train),'predictions.jsonl':'\n'.join(canonical(r) for r in rows)+'\n'}
    for name,text in outputs.items():
        p=OUT/name
        if p.exists():assert p.read_text()==text,'Refusing changed rerun artifact'
        else:p.write_text(text)
    print(json.dumps({e:{k:v[k] for k in ['brier','log_loss','paired_session_ci95']} for e,v in report['engines'].items()},indent=2))

if __name__=='__main__':main()
