"""Frozen May-fit/June-development logistic comparison, no July access."""
import hashlib
import json
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT
from level_probability_lab.companion_logistic import fit,predict


def main():
    source=ROOT/'data/companion_v02/may_june';out=ROOT/'data/companion_model_v01'
    out.mkdir(exist_ok=True)
    protocol=ROOT/'docs/COMPANION_TRAINING_V01.md'
    inputs={}
    tables=[];counts={}
    for month in ['may','june']:
        for kind in ['features','labels']:
            path=source/f'{kind}_{month}.parquet'
            inputs[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        f=pd.read_parquet(source/f'features_{month}.parquet');l=pd.read_parquet(source/f'labels_{month}.parquet')
        merged=f.merge(l,on='origin_id',validate='one_to_one')
        valid=merged.label_eligible & ~merged.tie_flag & merged.ts_block_available & merged.candle_features_complete
        counts[month]={'total':len(merged),'ties':int(merged.tie_flag.sum()),'excluded':int((~valid).sum()),'used':int(valid.sum())}
        tables.append(merged.loc[valid].copy())
    train,test=tables
    assert pd.to_datetime(train.label_available_at,utc=True).max()<pd.to_datetime(test.forecast_time_utc,utc=True).min()
    feature_columns=list(pd.read_parquet(source/'features_may.parquet').columns[5:])
    for frame in [train,test]:
        for day in range(2,6):frame[f'dow_{day}']=(frame.dow_ny==day).astype(float)
    feature_columns=[c for c in feature_columns if c!='dow_ny']+[f'dow_{d}' for d in range(2,6)]
    candle=[c for c in feature_columns if not c.startswith('ts_')]
    assert len(candle)==37 and len(feature_columns)==44
    models={};prediction={}
    for name,columns in [('candle',candle),('trades',feature_columns)]:
        model=fit(train[columns].to_numpy(float),train.y_kronos_wins.to_numpy(float))
        model['columns']=columns
        models[name]=model
    frozen={'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'inputs':inputs,
            'models':models,'train_win_frequency':float(train.y_kronos_wins.mean()),'counts':counts}
    frozen_text=json.dumps(frozen,indent=2)
    model_path=out/'frozen_model.json'
    if model_path.exists() and model_path.read_text()!=frozen_text:raise ValueError('Frozen model differs; use a new version')
    model_path.write_text(frozen_text)
    # June predictions happen only after the model artifact is fixed.
    prediction['climatology']=np.full(len(test),frozen['train_win_frequency'])
    for name,model in models.items():prediction[name]=predict(model,test[model['columns']].to_numpy(float))
    y=test.y_kronos_wins.to_numpy(float)
    ledger=test[['origin_id','forecast_time_utc','y_kronos_wins','actual_close_p5']].reset_index(drop=True)
    ledger['session']=ledger.forecast_time_utc.str[:10]
    baseline_errors=[];kronos_errors=[]
    for row in test.itertuples():
        package=json.loads((source/'input_packages'/(row.origin_id+'.json')).read_text())
        current=package['kronos_inputs']['candles'][-1]['close']
        future=np.median(np.asarray(package['forecast']['sampled_paths'])[:,4,3])
        baseline_errors.append(abs(current-row.actual_close_p5));kronos_errors.append(abs(future-row.actual_close_p5))
    ledger['unchanged_error']=baseline_errors;ledger['kronos_error']=kronos_errors
    metrics={}
    for name,p in prediction.items():
        ledger[name+'_probability']=p
        ledger[name+'_brier']=(p-y)**2
        ledger[name+'_gate_error']=np.where(p>=.5,kronos_errors,baseline_errors)
        clipped=np.clip(p,1e-15,1-1e-15)
        reliability=[]
        for low in [0,.2,.4,.6,.8]:
            mask=(p>=low)&(p<(low+.2) if low<.8 else p<=1)
            reliability.append({'lower':low,'n':int(mask.sum()),'mean_probability':float(p[mask].mean()) if mask.any() else None,'win_rate':float(y[mask].mean()) if mask.any() else None})
        metrics[name]={'brier':float(np.mean((p-y)**2)),
                       'log_loss':float(-np.mean(y*np.log(clipped)+(1-y)*np.log1p(-clipped))),
                       'accuracy':float(np.mean((p>=.5)==y)),
                       'gate_mae':float(ledger[name+'_gate_error'].mean()),'reliability':reliability}
    rng=np.random.default_rng(20260919);sessions=sorted(ledger.session.unique())
    draws=rng.integers(0,len(sessions),size=(2000,len(sessions)))
    comparisons={}
    for a,b in [('trades_brier','candle_brier'),('candle_brier','climatology_brier'),('trades_brier','climatology_brier'),('trades_gate_error','candle_gate_error')]:
        grouped=ledger.assign(delta=ledger[a]-ledger[b]).groupby('session').delta.agg(['sum','count']).reindex(sessions)
        boot=grouped['sum'].to_numpy()[draws].sum(axis=1)/grouped['count'].to_numpy()[draws].sum(axis=1)
        comparisons[a+' minus '+b]={'difference':float((ledger[a]-ledger[b]).mean()),'session_bootstrap_95':np.quantile(boot,[.025,.975]).tolist()}
    report={'scope':'June development evaluation, not untouched final test','counts':counts,
            'june_sessions':len(sessions),'may_win_frequency':frozen['train_win_frequency'],
            'june_win_frequency':float(y.mean()),'metrics':metrics,'comparisons':comparisons,
            'always_unchanged_mae':float(np.mean(baseline_errors)),'always_kronos_mae':float(np.mean(kronos_errors)),
            'frozen_model_sha256':hashlib.sha256(frozen_text.encode()).hexdigest()}
    ledger.to_csv(out/'june_predictions.csv',index=False)
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({**report,'metrics':{k:{a:b for a,b in v.items() if a!='reliability'} for k,v in metrics.items()}},indent=2))


if __name__=='__main__':main()
