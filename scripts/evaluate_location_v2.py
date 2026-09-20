"""Fixed distance-band analysis of the immutable v1 development ledgers."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from level_probability_lab.lab import ROOT
from level_probability_lab.location_bands import FAMILIES,BANDS,classify
from level_probability_lab.location_evaluation import interval,contrast

OLD=ROOT/'data/location_evaluation_v1'
OUT=ROOT/'data/location_evaluation_v2'


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inputs():
    if OUT.exists():raise RuntimeError('Preserve existing output; new run requires a new version')
    m=json.loads((OLD/'manifest.json').read_text())
    assert digest(OLD/'prediction_contexts.jsonl')==m['outputs']['prediction_contexts.jsonl']
    rows=[];equivalent=0
    with (OLD/'prediction_contexts.jsonl').open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);ctx=row['context'];features=classify(ctx)
            assert (features['sma_confluence_band']==BANDS[0])==(ctx['location_group']=='confluence')
            # Independent price-level formulas, not reuse of stored normalized distances.
            risk=ctx['risk'];price=ctx['reference'];distances={}
            for family in FAMILIES[:-1]:
                tf,kind=family.split('_');levels=[v for v in ctx['levels'] if v['timeframe']==tf and v['name'].startswith('SMA' if kind=='sma' else 'BB')]
                if all(v['value'] is not None for v in levels):
                    d=min(abs(price-v['value'])/risk for v in levels)
                    assert abs(d-features[family+'_distance_r'])<1e-10
                    distances[family]=[v['value'] for v in levels]
                assert (features[family+'_band']==BANDS[0])==any(v['near'] for v in levels)
            if 'hourly_sma' in distances and 'daily_sma' in distances:
                d=min(max(abs(price-h),abs(price-d),abs(h-d))/risk for h in distances['hourly_sma'] for d in distances['daily_sma'])
                assert abs(d-features['sma_confluence_distance_r'])<1e-10
            equivalent+=1
            rows.append(dict(forecast_id=row['forecast_id'],context_id=row['context_id'],date=row['date'],month=row['date'][:7],**features))
    frame=pd.DataFrame(rows);assert len(frame)==2214 and frame.forecast_id.is_unique
    coverage=[]
    for family in FAMILIES:
        for label in BANDS:
            sub=frame.loc[frame[family+'_band']==label]
            months={month:dict(origins=len(sub.loc[sub.month==month]),sessions=int(sub.loc[sub.month==month].date.nunique())) for month in ['2026-05','2026-06']}
            coverage.append(dict(family=family,band=label,origins=len(sub),sessions=int(sub.date.nunique()),months=months,
                support=len(sub)>=100 and sub.date.nunique()>=10 and all(v['origins']>=30 and v['sessions']>=5 for v in months.values())))
    OUT.mkdir();frame.to_csv(OUT/'classifications.csv',index=False)
    (OUT/'coverage.json').write_text(json.dumps(coverage,indent=2))
    protocol=ROOT/'docs/LOCATION_EVALUATION_V2_PROTOCOL.md';(OUT/'protocol.md').write_bytes(protocol.read_bytes())
    manifest=dict(parent_manifest_sha256=digest(OLD/'manifest.json'),contexts_sha256=digest(OLD/'prediction_contexts.jsonl'),outcomes_sha256=m['outputs']['outcomes.csv'],
                  protocol_sha256=digest(protocol),classification_sha256=digest(OUT/'classifications.csv'),coverage_sha256=digest(OUT/'coverage.json'),
                  independent_formula_and_v1_membership_checks=equivalent,
                  code={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__).resolve(),ROOT/'src/level_probability_lab/location_bands.py',ROOT/'src/level_probability_lab/location_evaluation.py']})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(coverage,indent=2))


def score():
    if (OUT/'report.json').exists():raise RuntimeError('Final report already exists')
    m=json.loads((OUT/'manifest.json').read_text())
    assert digest(OUT/'classifications.csv')==m['classification_sha256'] and digest(OUT/'coverage.json')==m['coverage_sha256']
    assert digest(OLD/'outcomes.csv')==m['outcomes_sha256']
    features=pd.read_csv(OUT/'classifications.csv');old=pd.read_csv(OLD/'outcomes.csv')
    df=old.merge(features.drop(columns=['date','month']),on=['forecast_id','context_id'],how='left',validate='many_to_one')
    assert len(df)==13284 and not df[[f+'_band' for f in FAMILIES]].isna().any().any()
    df.to_csv(OUT/'outcomes.csv',index=False)
    coverage=json.loads((OUT/'coverage.json').read_text());results=[];comparisons=[]
    for period,part in [('pooled',df),('May',df.loc[df.month=='2026-05']),('June',df.loc[df.month=='2026-06'])]:
        for horizon in [5,60]:
            for ratio in [1,2,3]:
                block=part.loc[(part.horizon==horizon)&(part.ratio==ratio)].copy()
                block['complete']=(block.kronos_status=='complete').astype(int)
                block['target']=(block.kronos_outcome=='target_first').astype(int)
                block['paired']=((block.kronos_status=='complete')&(block.always_up_status=='complete')&(block.always_down_status=='complete')).astype(int)
                block['coin']=.5*((block.always_up_outcome=='target_first').astype(int)+(block.always_down_outcome=='target_first').astype(int))*block.paired
                block['excess']=block.paired*block.target-block.coin
                for family in FAMILIES:
                    for label in BANDS:
                        sub=block.loc[block[family+'_band']==label];valid=sub.loc[sub.complete==1];paired=sub.loc[sub.paired==1]
                        controls={}
                        for engine in ['always_up','always_down','momentum5']:
                            eligible=sub.loc[sub[engine+'_status']=='complete']
                            controls[engine]=dict(complete=len(eligible),target_rate=float((eligible[engine+'_outcome']=='target_first').mean()) if len(eligible) else None,
                                counts=eligible[engine+'_outcome'].value_counts().to_dict(),excluded=len(sub)-len(eligible))
                        results.append(dict(period=period,horizon=horizon,ratio=ratio,family=family,band=label,
                            origins=len(sub),sessions=int(sub.date.nunique()),complete=len(valid),excluded=len(sub)-len(valid),
                            counts=valid.kronos_outcome.value_counts().to_dict(),target_rate=interval(sub,'target','complete',dates=block.date.unique()),
                            paired_origins=len(paired),coin_rate=float(paired.coin.mean()) if len(paired) else None,
                            excess_vs_coin=interval(sub,'excess','paired',dates=block.date.unique()),controls=controls))
                        if label in BANDS[:3]:
                            compared=block.copy();compared['group']='other'
                            compared.loc[compared[family+'_band']==label,'group']='confluence'
                            compared.loc[compared[family+'_band']=='over_2R','group']='no_confluence'
                            comparisons.append(dict(period=period,horizon=horizon,ratio=ratio,family=family,band=label,reference_band='over_2R',
                                raw_difference=contrast(compared,'target','complete'),excess_difference=contrast(compared,'excess','paired')))
        print(period+' summaries complete',flush=True)
    report=dict(scope='Post-hoc May/June development, no fresh holdout',coverage=coverage,results=results,comparisons=comparisons)
    (OUT/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    pd.json_normalize(results).to_csv(OUT/'summary.csv',index=False)
    pd.json_normalize(comparisons).to_csv(OUT/'comparisons.csv',index=False)
    # Independent join/partition/denominator checks; inherited outcome columns must be identical.
    pd.testing.assert_frame_equal(df[old.columns],old)
    for period in ['pooled','May','June']:
        for h in [5,60]:
            for ratio in [1,2,3]:
                for family in FAMILIES:
                    parts=[r for r in results if (r['period'],r['horizon'],r['ratio'],r['family'])==(period,h,ratio,family)]
                    assert sum(v['origins'] for v in parts)=={'pooled':2214,'May':1080,'June':1134}[period]
    for row in results:
        assert sum(row['counts'].values())==row['complete']
        if row['complete']:assert abs(row['target_rate']['value']-row['counts'].get('target_first',0)/row['complete'])<1e-12
    verification=dict(passed=True,origins=2214,joined_rows=len(df),summaries=len(results),comparisons=len(comparisons),v1_outcomes_unchanged=True,
        context_formulas_and_v1_memberships_verified=m['independent_formula_and_v1_membership_checks'])
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2))
    m['outputs']={p.name:digest(p) for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(verification))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['inputs','score']);args=parser.parse_args()
    inputs() if args.phase=='inputs' else score()
