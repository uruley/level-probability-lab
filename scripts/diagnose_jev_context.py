"""Read saved answers only. No credentials, network, fitting or threshold search."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.jev_companion import parse_typesafe, CLASSES
from level_probability_lab.bull_bear_probability import multiclass_losses

ROOT = Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'data/jev_context_sample_v1'
    manifest=json.loads((folder/'manifest.json').read_text())
    report=json.loads((folder/'report.json').read_text())
    truth={r['origin']:r for r in report['origins']}
    contexts={}
    with (ROOT/'data/location_evaluation_v1/prediction_contexts.jsonl').open() as f:
        for line in f:
            r=json.loads(line)
            if r['origin'] in truth: contexts[r['origin']]=r
    rows=[]
    for entry in manifest['entries']:
        origin=entry['origin']; y=CLASSES.index(truth[origin]['label'])
        ctx=contexts[origin]
        body={k:v for k,v in ctx.items() if k!='context_id'}
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()
        if digest!=entry['context_id']: raise ValueError('Context integrity failure')
        context=ctx['context']; risk=context['risk']
        row=dict(origin=origin,session=origin[:10],actual=CLASSES[y])
        for arm in ('kronos_only','with_context'):
            spec=entry['packages'][arm]; raw=(folder/spec['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=spec['sha256']: raise ValueError('Package changed')
            paths=list((folder/'responses'/Path(spec['file']).stem).glob('*.response.json'))
            if len(paths)!=1: raise ValueError('Expected one saved response')
            result=parse_typesafe(json.loads(paths[0].read_text()))
            p=np.array([result['scores'][c] for c in CLASSES])
            loss=multiclass_losses([y],p[None,:])[0]
            row.update({arm+'_choice':result['choice'],arm+'_p_actual':float(p[y]),
                arm+'_brier':float(loss[0]),arm+'_log_loss':float(loss[1]),
                arm+'_scores':p.tolist()})
        row['choice_changed']=row['kronos_only_choice']!=row['with_context_choice']
        row['distribution_changed']=not np.allclose(row['kronos_only_scores'],row['with_context_scores'],rtol=0,atol=1e-12)
        for metric in ('brier','log_loss'):
            row[metric+'_delta']=row['with_context_'+metric]-row['kronos_only_'+metric]
        row['became_correct']=row['choice_changed'] and row['with_context_choice']==row['actual']
        row['became_incorrect']=row['choice_changed'] and row['kronos_only_choice']==row['actual']
        # Fixed market-context-v1 proximity, NOT a new optimized distance.
        for group in ('higher_timeframe','hourly_sma','daily_sma','hourly_bb','daily_bb','previous_day'):
            levels=[v for v in context['levels'] if
                (group=='higher_timeframe' and v['timeframe'] in ('hourly','daily')) or
                (group=='previous_day' and v['name'].startswith('Previous')) or
                (group.endswith('_sma') and v['timeframe']==group.split('_')[0] and v['name'].startswith('SMA')) or
                (group.endswith('_bb') and v['timeframe']==group.split('_')[0] and v['name'].startswith('BB'))]
            distances=[abs((context['reference']-v['value'])/risk) for v in levels
                if v['value'] is not None and risk is not None and risk>0]
            row[group]='near' if any(d<=.5 for d in distances) else 'far' if len(distances)==len(levels) and levels else 'unknown'
        rows.append(row)
    frame=pd.DataFrame(rows)
    def summarize(g):
        return dict(n=len(g),sessions=g.session.nunique(),class_counts=g.actual.value_counts().to_dict(),
            distribution_changes=int(g.distribution_changed.sum()),choice_changes=int(g.choice_changed.sum()),
            became_correct=int(g.became_correct.sum()),became_incorrect=int(g.became_incorrect.sum()),
            brier_helped=int((g.brier_delta < -1e-12).sum()),brier_hurt=int((g.brier_delta > 1e-12).sum()),
            mean_brier_delta=float(g.brier_delta.mean()),mean_log_loss_delta=float(g.log_loss_delta.mean()))
    groups=[]
    for key in ('higher_timeframe','hourly_sma','daily_sma','hourly_bb','daily_bb','previous_day'):
        for value,g in frame.groupby(key): groups.append(dict(category=key,proximity=value,**summarize(g)))
    concentration={}
    for arm in ('kronos_only','with_context'):
        column=arm+'_log_loss'; ordered=frame.sort_values(column,ascending=False)
        total=float(frame[column].sum())
        concentration[arm]=dict(total_log_loss=total,worst_one_share=float(ordered.iloc[0][column]/total),
            worst_three_share=float(ordered.head(3)[column].sum()/total),
            zero_mass_actual=int((frame[arm+'_p_actual']==0).sum()),
            worst=ordered.head(3)[['origin','actual',arm+'_choice',arm+'_p_actual',column]].to_dict('records'))
    influence=[]
    for session,g in frame.groupby('session'):
        remaining=frame[frame.session!=session]
        influence.append(dict(omitted_session=session,remaining_brier_delta=float(remaining.brier_delta.mean()),
            remaining_log_loss_delta=float(remaining.log_loss_delta.mean())))
    result=dict(overall=summarize(frame),groups=groups,loss_concentration=concentration,
        largest_log_loss_changes=frame.loc[frame.log_loss_delta.abs().sort_values(ascending=False).index].head(5).to_dict('records'),
        leave_one_session_out=influence,threshold='existing 0.5R; higher_timeframe excludes session high/low',
        limits='post-hoc descriptive diagnosis; groups overlap; no prompt tuning or subgroup promotion',network_calls=0)
    out=folder/'diagnosis';out.mkdir(exist_ok=True)
    frame.to_json(out/'origins.json',orient='records',indent=2)
    (out/'report.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
