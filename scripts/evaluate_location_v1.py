"""Run the frozen May/June location study using archived forecasts only."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, load_day
from level_probability_lab.calendar import session_schedule
from level_probability_lab.market_context import load_history, snapshot
from level_probability_lab.touch_experiment import setup, observe
from level_probability_lab.location_evaluation import score_path, interval, contrast


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def summarize(out,df,flags,coverage,audit):
    results=[];comparisons=[]
    for period,part in [('pooled',df),('May',df.loc[df.month=='2026-05']),('June',df.loc[df.month=='2026-06'])]:
        for horizon in [5,60]:
            for ratio in [1,2,3]:
                block=part.loc[(part.horizon==horizon)&(part.ratio==ratio)].copy()
                block['complete']=(block.kronos_status=='complete').astype(int)
                block['target']=(block.kronos_outcome=='target_first').astype(int)
                block['paired']=((block.kronos_status=='complete')&(block.always_up_status=='complete')&(block.always_down_status=='complete')).astype(int)
                block['excess']=block.paired*(block.target-.5*((block.always_up_outcome=='target_first').astype(int)+(block.always_down_outcome=='target_first').astype(int)))
                groups=[(g,block.loc[block.group==g]) for g in ['confluence','no_confluence','unknown']]
                groups += [(flag,block.loc[block[flag]==True]) for flag in flags]
                for group,sub in groups:
                    for engine in ['kronos','always_up','always_down','momentum5']:
                        valid=sub.loc[sub[engine+'_status']=='complete']
                        counts=valid[engine+'_outcome'].value_counts().to_dict()
                        temp=sub.assign(numerator=(sub[engine+'_outcome']=='target_first').astype(int),denominator=(sub[engine+'_status']=='complete').astype(int))
                        estimate=interval(temp,'numerator','denominator',dates=block.date.unique())
                        results.append(dict(period=period,horizon=horizon,ratio=ratio,group=group,engine=engine,origins=len(sub),complete=len(valid),
                            missing=int((sub[engine+'_status']=='incomplete').sum()),no_setup=int((sub[engine+'_status']=='no_setup').sum()),
                            counts=counts,target_rate=estimate,mean_touch_minutes=float(valid.loc[valid[engine+'_outcome'].isin(['target_first','stop_first','ambiguous']),engine+'_minutes'].mean()) if valid[engine+'_outcome'].isin(['target_first','stop_first','ambiguous']).any() else None))
                    comparisons.append(dict(period=period,horizon=horizon,ratio=ratio,group=group,paired_origins=int(sub.paired.sum()),excess_vs_coin=interval(sub,'excess','paired',dates=block.date.unique())))
                comparisons.append(dict(period=period,horizon=horizon,ratio=ratio,group='confluence_minus_no_confluence',
                    target_rate_difference=contrast(block,'target','complete'),excess_difference=contrast(block,'excess','paired')))
    report=dict(scope='Exploratory May/June development; no tuning or July outcomes',origins=2214,sessions=41,coverage=coverage,audit=audit,results=results,comparisons=comparisons)
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    pd.json_normalize(results).to_csv(out/'summary.csv',index=False)
    pd.json_normalize(comparisons).to_csv(out/'comparisons.csv',index=False)

def main():
    out=ROOT/'data/location_evaluation_v1'
    if out.exists():raise RuntimeError('Output already exists; preserve it and use a new version for reruns')
    archive=ROOT/'data/kronos_baseline_v1';config_path=archive/'frozen_config.json'
    cfg=json.loads(config_path.read_text());source=ROOT/cfg['source']
    assert (cfg['lookback'],cfg['horizon'],cfg['sample_count'],cfg['seed'],cfg['stride_minutes'])==(120,5,25,42,5)
    assert digest(source)==cfg['source_sha256'],'Source changed'
    dates=[str(pd.Timestamp(d).date()) for d in session_schedule('2026-05-01','2026-06-30').index]
    history=load_history(source,'2026-06-30')
    out.mkdir();protocol=ROOT/'docs/LOCATION_EVALUATION_V1_PROTOCOL.md'
    (out/'protocol.md').write_bytes(protocol.read_bytes())
    manifest=dict(protocol_sha256=digest(protocol),source_sha256=cfg['source_sha256'],config_sha256=digest(config_path),
        files=[],code={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__).resolve(),ROOT/'src/level_probability_lab/location_evaluation.py',ROOT/'src/level_probability_lab/market_context.py',ROOT/'src/level_probability_lab/touch_experiment.py']})
    rows=[];coverage=[];audit=[]
    with (out/'prediction_contexts.jsonl').open('x',encoding='utf-8') as contexts:
        for day in dates:
            bars=load_day(source,day);bytime=bars.set_index('bar_start')
            paths=sorted((archive/'forecasts/base').glob(day.replace('-','')+'T*.json'))
            expected=pd.date_range(bars.iloc[0].session_open+pd.Timedelta(minutes=119),bars.iloc[0].session_close-pd.Timedelta(minutes=6),freq='5min')
            origins=[]
            for index,path in enumerate(paths):
                r=json.loads(path.read_text());origin=pd.Timestamp(r['origin']);origins.append(origin)
                assert r['date']==day and r['model']=='base'
                visible=bars.loc[bars.bar_start<=origin];window=visible.tail(120)
                assert len(window)==120 and list(window.bar_start)==list(pd.date_range(window.iloc[0].bar_start,origin,freq='min'))
                input_hash=hashlib.sha256(window[['bar_start','open','high','low','close','volume']].to_csv(index=False).encode()).hexdigest()
                assert input_hash==r['input_sha256']
                arr=np.asarray(r['sampled_ohlc']);assert arr.shape==(25,5,4) and np.isfinite(arr).all()
                cutoff=origin+pd.Timedelta(minutes=1)
                assert list(pd.to_datetime(r['targets'],utc=True))==list(pd.date_range(cutoff,periods=5,freq='min'))
                record=dict(input_window=window[['open','high','low','close']].to_dict('records'),sampled_paths=r['sampled_ohlc'])
                frozen=setup(record);risk=frozen['risk'];reference=frozen['reference']
                ctx=snapshot(history,visible,risk,frozen['direction'])
                assert all(v['available_at'] is None or pd.Timestamp(v['available_at'])<=cutoff for v in ctx['levels'])
                if index==0:
                    trimmed={k:v.loc[v.end<=cutoff].copy() for k,v in history.items()}
                    assert snapshot(trimmed,visible,risk,frozen['direction'])==ctx
                    for key in history:
                        for item in ctx['history_evidence'][key]:assert pd.Timestamp(item['end'])<=cutoff
                fid='baseline-v1|base|'+r['origin'];forecast_hash=digest(path)
                manifest['files'].append(dict(path=str(path.relative_to(ROOT)),sha256=forecast_hash))
                inputs=dict(forecast_id=fid,date=day,origin=r['origin'],input_sha256=input_hash,forecast_sha256=forecast_hash,context=ctx,frozen_setup=frozen)
                text=json.dumps(inputs,sort_keys=True,allow_nan=False)
                context_id=hashlib.sha256(text.encode()).hexdigest()
                contexts.write(json.dumps(dict(context_id=context_id,**inputs),allow_nan=False)+'\n');contexts.flush()
                flags={}
                for tf in ['hourly','daily']:
                    for kind in ['sma','bb']:
                        levels=[v for v in ctx['levels'] if v['timeframe']==tf and v['name'].startswith('SMA' if kind=='sma' else 'BB')]
                        flags[f'near_{tf}_{kind}']=True if any(v['near'] for v in levels) else False if all(v['near'] is not None for v in levels) else None
                direction={'up':1,'down':-1,'neutral':0}[frozen['direction']]
                momentum=int(np.sign(reference-float(window.iloc[-6].close)))
                directions=dict(kronos=direction,always_up=1,always_down=-1,momentum5=momentum)
                for horizon in [5,60]:
                    deadline=min(cutoff+pd.Timedelta(minutes=horizon),bars.iloc[0].session_close)
                    minutes=int((deadline-cutoff).total_seconds()/60)
                    grid=pd.date_range(cutoff,deadline,freq='min',inclusive='left')
                    future=bytime.reindex(grid)[['open','high','low','close']].to_numpy(float)
                    for ratio in [1,2,3]:
                        row=dict(forecast_id=fid,context_id=context_id,date=day,month=day[:7],origin=r['origin'],
                            group=ctx['location_group'],trend_agreement=ctx['trend_agreement'],horizon=horizon,
                            ratio=ratio,reference=reference,risk=risk,deadline=deadline.isoformat(),available_minutes=minutes,**flags)
                        for engine,d in directions.items():
                            value=score_path(future,reference,risk,d,ratio,minutes)
                            if horizon==60 and value['outcome']=='neither':value['outcome']='expired'
                            row.update({engine+'_'+k:v for k,v in value.items()})
                            row[engine+'_direction']=d
                            row[engine+'_target']=reference+d*ratio*risk if d else None
                            row[engine+'_stop']=reference-d*risk if d else None
                        if index==0 and frozen['status']=='ready':
                            official=observe(frozen,r['targets'],bars,horizon==60)[ratio-1]
                            assert official['status']==row['kronos_status'] and official['outcome']==row['kronos_outcome']
                            assert official['minutes_to_resolution']==row['kronos_minutes']
                        rows.append(row)
                if index==0:audit.append(dict(date=day,input_hash_verified=True,context_cutoff_verified=True,replay_outcomes_matched=True))
            assert origins==list(expected),f'Coverage mismatch {day}'
            coverage.append(dict(date=day,forecasts=len(paths)))
            print(day+': '+str(len(paths))+' forecasts scored',flush=True)
    df=pd.DataFrame(rows);df.to_csv(out/'outcomes.csv',index=False)
    assert len(df)==2214*6 and len(coverage)==41
    summarize(out,df,flags,coverage,audit)
    manifest['outputs']={p.name:digest(p) for p in out.iterdir() if p.is_file()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Complete: '+str(out),flush=True)


if __name__=='__main__':main()
