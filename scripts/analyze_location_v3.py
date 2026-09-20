"""August replication: freeze as-of features before joining realized outcomes."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, load_day
from level_probability_lab.market_context import load_history, snapshot
from level_probability_lab.touch_experiment import setup, observe
from level_probability_lab.location_bands import FAMILIES, BANDS, classify
from level_probability_lab.location_evaluation import score_path, interval, contrast
from level_probability_lab.baseline_study import forecast_file, write_json


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def checked_features(ctx):
    features = classify(ctx)
    assert (features['sma_confluence_band'] == BANDS[0]) == (ctx['location_group'] == 'confluence')
    prices = {}; price = ctx['reference']; risk = ctx['risk']
    for family in FAMILIES[:-1]:
        tf, kind = family.split('_')
        levels = [v for v in ctx['levels'] if v['timeframe'] == tf and v['name'].startswith('SMA' if kind == 'sma' else 'BB')]
        if all(v['value'] is not None for v in levels):
            prices[family] = [v['value'] for v in levels]
            expected = min(abs(price-v)/risk for v in prices[family])
            assert abs(expected-features[family+'_distance_r']) < 1e-10
        assert (features[family+'_band'] == BANDS[0]) == any(v['near'] for v in levels)
    if 'hourly_sma' in prices and 'daily_sma' in prices:
        expected = min(max(abs(price-h),abs(price-d),abs(h-d))/risk
                       for h in prices['hourly_sma'] for d in prices['daily_sma'])
        assert abs(expected-features['sma_confluence_distance_r']) < 1e-10
    return features


def contexts(out, source, config):
    history = load_history(source, '2026-08-31')
    rows=[]; files=[]; previous=None
    with (out/'prediction_contexts.jsonl').open('x', encoding='utf-8') as ledger:
        for item in config['origins']:
            day=item['date']; origin=pd.Timestamp(item['origin']); cutoff=origin+pd.Timedelta(minutes=1)
            if day != previous:
                bars=load_day(source, day); previous=day
            visible=bars.loc[bars.bar_start<=origin]; window=visible.tail(120)
            assert list(window.bar_start) == list(pd.date_range(origin-pd.Timedelta(minutes=119),origin,freq='min'))
            path=forecast_file(out,'base',item['origin']); r=json.loads(path.read_text())
            assert all(r[k]==v for k,v in item.items()) and r['model']=='base'
            ih=hashlib.sha256(window[['bar_start','open','high','low','close','volume']].to_csv(index=False).encode()).hexdigest()
            assert ih==r['input_sha256'] and r['origin_close']==float(window.iloc[-1].close)
            assert r['targets']==[t.isoformat() for t in pd.date_range(cutoff,periods=5,freq='min')]
            arr=np.asarray(r['sampled_ohlc']); assert arr.shape==(25,5,4) and np.isfinite(arr).all()
            frozen=setup(dict(input_window=window[['open','high','low','close']].to_dict('records'),sampled_paths=r['sampled_ohlc']))
            ctx=snapshot(history,visible,frozen['risk'],frozen['direction'])
            assert all(v['available_at'] is None or pd.Timestamp(v['available_at'])<=cutoff for v in ctx['levels'])
            for evidence in ctx['history_evidence'].values():
                assert all(pd.Timestamp(v['end'])<=cutoff for v in evidence)
            if origin==bars.iloc[119].bar_start:
                trimmed={k:v.loc[v.end<=cutoff].copy() for k,v in history.items()}
                assert snapshot(trimmed,visible,frozen['risk'],frozen['direction'])==ctx
            features=checked_features(ctx); fh=digest(path)
            inputs=dict(forecast_id='location-v3|base|'+r['origin'],date=day,origin=r['origin'],input_sha256=ih,
                forecast_sha256=fh,context=ctx,frozen_setup=frozen,
                momentum_direction=int(np.sign(float(window.iloc[-1].close)-float(window.iloc[-6].close))))
            cid=hashlib.sha256(json.dumps(inputs,sort_keys=True,allow_nan=False).encode()).hexdigest()
            ledger.write(json.dumps(dict(context_id=cid,**inputs),allow_nan=False)+'\n'); ledger.flush()
            rows.append(dict(forecast_id=inputs['forecast_id'],context_id=cid,date=day,month=day[:7],**features))
            files.append(dict(path=str(path.relative_to(ROOT)),sha256=fh))
            if len(rows)%54==0: print(day+': contexts frozen',flush=True)
    frame=pd.DataFrame(rows); assert len(frame)==1134 and frame.forecast_id.is_unique
    frame.to_csv(out/'classifications.csv',index=False)
    reference=ROOT/'data/location_evaluation_v2'
    manifest=json.loads((reference/'manifest.json').read_text())
    assert digest(reference/'manifest.json')==config['reference_manifest_sha256']
    assert digest(reference/'classifications.csv')==manifest['outputs']['classifications.csv']
    old=pd.read_csv(reference/'classifications.csv')
    combined=pd.concat([old,frame],ignore_index=True); coverage=[]
    for family in FAMILIES:
        for band in BANDS:
            sub=combined.loc[combined[family+'_band']==band]
            months={month:dict(origins=len(sub.loc[sub.month==month]),sessions=int(sub.loc[sub.month==month].date.nunique()))
                    for month in ['2026-05','2026-06','2026-08']}
            coverage.append(dict(family=family,band=band,months=months,
                support=len(sub)>=100 and sub.date.nunique()>=10 and all(v['origins']>=30 and v['sessions']>=5 for v in months.values())))
    write_json(out/'coverage.json',coverage,True)
    write_json(out/'inputs_manifest.json',dict(files=files,origins=len(rows),
        outputs={p:digest(out/p) for p in ['prediction_contexts.jsonl','classifications.csv','coverage.json']}),True)


def outcomes(out, source):
    manifest=json.loads((out/'inputs_manifest.json').read_text())
    for name,sha in manifest['outputs'].items(): assert digest(out/name)==sha
    rows=[]; previous=None; audit=[]
    with (out/'prediction_contexts.jsonl').open(encoding='utf-8') as ledger:
        for line in ledger:
            c=json.loads(line); cid=c.pop('context_id')
            assert hashlib.sha256(json.dumps(c,sort_keys=True,allow_nan=False).encode()).hexdigest()==cid
            day=c['date']; origin=pd.Timestamp(c['origin']); cutoff=origin+pd.Timedelta(minutes=1)
            if day!=previous:
                bars=load_day(source,day); bytime=bars.set_index('bar_start'); previous=day
            frozen=c['frozen_setup']; risk=frozen['risk']; reference=frozen['reference']
            direction={'up':1,'down':-1,'neutral':0}[frozen['direction']]
            directions=dict(kronos=direction,always_up=1,always_down=-1,momentum5=c['momentum_direction'])
            targets=[t.isoformat() for t in pd.date_range(cutoff,periods=5,freq='min')]
            check=origin in [bars.iloc[119].bar_start,bars.iloc[-6].bar_start]
            for horizon in [5,60]:
                deadline=min(cutoff+pd.Timedelta(minutes=horizon),bars.iloc[0].session_close)
                minutes=int((deadline-cutoff).total_seconds()/60)
                future=bytime.reindex(pd.date_range(cutoff,deadline,freq='min',inclusive='left'))[['open','high','low','close']].to_numpy(float)
                for ratio in [1,2,3]:
                    row=dict(forecast_id=c['forecast_id'],context_id=cid,date=day,month=day[:7],origin=c['origin'],
                        horizon=horizon,ratio=ratio,reference=reference,risk=risk,deadline=deadline.isoformat(),available_minutes=minutes)
                    for engine,d in directions.items():
                        value=score_path(future,reference,risk,d,ratio,minutes)
                        if horizon==60 and value['outcome']=='neither': value['outcome']='expired'
                        row.update({engine+'_'+k:v for k,v in value.items()})
                        row[engine+'_direction']=d; row[engine+'_target']=reference+d*ratio*risk if d else None
                        row[engine+'_stop']=reference-d*risk if d else None
                        if check and d:
                            # Replay observer uses its own chronological touch implementation.
                            alternate=dict(frozen,direction='up' if d==1 else 'down',status='ready',
                                setups=[dict(ratio=q,target=reference+d*q*risk,stop=reference-d*risk) for q in [1,2,3]])
                            actual=observe(alternate,targets,bars,horizon==60)[ratio-1]
                            assert (actual['status'],actual['outcome'],actual['minutes_to_resolution'])==(value['status'],value['outcome'],value['minutes'])
                            audit.append(dict(date=day,origin=c['origin'],engine=engine,horizon=horizon,ratio=ratio))
                    rows.append(row)
    df=pd.DataFrame(rows); features=pd.read_csv(out/'classifications.csv')
    assert len(df)==1134*6
    df=df.merge(features.drop(columns=['date','month']),on=['forecast_id','context_id'],validate='many_to_one')
    assert len(df)==6804 and not df[[f+'_band' for f in FAMILIES]].isna().any().any()
    df.to_csv(out/'outcomes.csv',index=False)
    write_json(out/'replay_checks.json',audit,True)
    return df


def summarize(out,df):
    results=[]; comparisons=[]
    for horizon in [5,60]:
        for ratio in [1,2,3]:
            block=df.loc[(df.horizon==horizon)&(df.ratio==ratio)].copy()
            block['complete']=(block.kronos_status=='complete').astype(int)
            block['target']=(block.kronos_outcome=='target_first').astype(int)
            block['paired']=((block.kronos_status=='complete')&(block.always_up_status=='complete')&(block.always_down_status=='complete')).astype(int)
            block['coin']=.5*((block.always_up_outcome=='target_first').astype(int)+(block.always_down_outcome=='target_first').astype(int))*block.paired
            block['excess']=block.paired*block.target-block.coin
            for family in FAMILIES:
                for label in BANDS:
                    sub=block.loc[block[family+'_band']==label]; valid=sub.loc[sub.complete==1]; paired=sub.loc[sub.paired==1]
                    controls={}
                    for engine in ['always_up','always_down','momentum5']:
                        eligible=sub.loc[sub[engine+'_status']=='complete']
                        controls[engine]=dict(complete=len(eligible),target_rate=float((eligible[engine+'_outcome']=='target_first').mean()) if len(eligible) else None,
                            counts=eligible[engine+'_outcome'].value_counts().to_dict(),excluded=len(sub)-len(eligible))
                    results.append(dict(period='August',horizon=horizon,ratio=ratio,family=family,band=label,origins=len(sub),sessions=int(sub.date.nunique()),
                        complete=len(valid),excluded=len(sub)-len(valid),counts=valid.kronos_outcome.value_counts().to_dict(),
                        target_rate=interval(sub,'target','complete',dates=block.date.unique()),paired_origins=len(paired),
                        coin_rate=float(paired.coin.mean()) if len(paired) else None,
                        excess_vs_coin=interval(sub,'excess','paired',dates=block.date.unique()),controls=controls))
                    if label in BANDS[:3]:
                        compared=block.copy(); compared['group']='other'
                        compared.loc[compared[family+'_band']==label,'group']='confluence'
                        compared.loc[compared[family+'_band']=='over_2R','group']='no_confluence'
                        comparisons.append(dict(period='August',horizon=horizon,ratio=ratio,family=family,band=label,reference_band='over_2R',
                            raw_difference=contrast(compared,'target','complete'),excess_difference=contrast(compared,'excess','paired')))
    for h in [5,60]:
        for ratio in [1,2,3]:
            for family in FAMILIES:
                assert sum(r['origins'] for r in results if (r['horizon'],r['ratio'],r['family'])==(h,ratio,family))==1134
    for r in results:
        assert sum(r['counts'].values())==r['complete']
        if r['complete']: assert abs(r['target_rate']['value']-r['counts'].get('target_first',0)/r['complete'])<1e-12
    reference=ROOT/'data/location_evaluation_v2'; manifest=json.loads((reference/'manifest.json').read_text())
    assert digest(reference/'report.json')==manifest['outputs']['report.json']
    old=json.loads((reference/'report.json').read_text())
    report=dict(scope='Frozen August development replication; previously inspected, not holdout',origins=1134,sessions=21,
        coverage=json.loads((out/'coverage.json').read_text()),results=results,comparisons=comparisons,
        reference_results=old['results'],reference_comparisons=old['comparisons'])
    write_json(out/'report.json',report,True)
    pd.json_normalize(results).to_csv(out/'summary.csv',index=False)
    pd.json_normalize(comparisons).to_csv(out/'comparisons.csv',index=False)
    write_json(out/'verification.json',dict(passed=True,origins=1134,sessions=21,outcome_rows=len(df),summaries=len(results),
        comparisons=len(comparisons),replay_checks=len(json.loads((out/'replay_checks.json').read_text())),
        incomplete_kronos_rows=int((df.kronos_status=='incomplete').sum()),
        context_hashes_and_cutoffs=True,independent_price_formulas=True,partitions_and_denominators=True),True)


def analyze(out,source,config):
    if (out/'report.json').exists(): raise RuntimeError('Preserve completed report')
    if not (out/'inputs_manifest.json').exists(): contexts(out,source,config)
    # A partial analysis is kept for diagnosis rather than silently overwritten.
    if (out/'outcomes.csv').exists(): raise RuntimeError('Partial scoring output exists; inspect before resuming')
    df=outcomes(out,source)
    summarize(out,df)
    write_json(out/'manifest.json',dict(config_sha256=digest(out/'frozen_config.json'),
        outputs={p.name:digest(p) for p in out.iterdir() if p.is_file() and p.name not in ['manifest.json','progress.json','forecast.lock']}),True)
    print('August scoring and verification complete',flush=True)
