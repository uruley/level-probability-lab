"""Frozen compact-feature walk-forward study on May; June used development check."""
import hashlib
import json
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT
from level_probability_lab.companion_logistic import fit,predict


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(y,p):
    q=np.clip(p,1e-15,1-1e-15)
    return {'brier':float(np.mean((p-y)**2)),'log_loss':float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q))),
            'accuracy':float(np.mean((p>=.5)==y))}


def interval(delta,dates):
    g=pd.DataFrame({'d':delta,'date':dates}).groupby('date').d.agg(['sum','count'])
    draw=np.random.default_rng(20260919).integers(0,len(g),size=(2000,len(g)))
    samples=g['sum'].to_numpy()[draw].sum(1)/g['count'].to_numpy()[draw].sum(1)
    return {'difference':float(np.mean(delta)),'ci95':np.quantile(samples,[.025,.975]).tolist(),'sessions':len(g)}


def main():
    source=ROOT/'data/companion_v02/may_june';out=ROOT/'data/companion_small_v02';out.mkdir(exist_ok=True)
    metadata={};tables={};exclusions={}
    for month in ['may','june']:
        fpath=source/f'features_{month}.parquet';lpath=source/f'labels_{month}.parquet'
        x=pd.read_parquet(fpath).merge(pd.read_parquet(lpath),on='origin_id',validate='one_to_one')
        mask=x.label_eligible & ~x.tie_flag & x.ts_block_available & x.candle_features_complete
        exclusions[month]=int((~mask).sum());x=x.loc[mask].copy();x['session']=x.forecast_time_utc.str[:10]
        tables[month]=x.sort_values('forecast_time_utc').reset_index(drop=True)
        metadata[fpath.name]=sha(fpath);metadata[lpath.name]=sha(lpath)
    core=[f'k_d{i}_atr' for i in range(1,6)]+['k_path_iqr5_atr','k_path_frac_up5']
    compact=core+['tod_frac_session','ret_1m','ret_5m_sum','atr14_over_close','rvol_20','nasdaq_vol_ratio_20','bb_pctb']
    trade=[c for c in tables['may'].columns if c.startswith('ts_') and c!='ts_block_available']
    assert len(trade)==7
    sets={'forecast':core,'compact':compact,'compact_trades':compact+trade}
    may=tables['may'];days=sorted(may.session.unique());assert len(days)==20
    oof=[];fold_models={};fold_results=[]
    for number,(n,end) in enumerate([(10,15),(15,20)],1):
        train=may.loc[may.session.isin(days[:n])];valid=may.loc[may.session.isin(days[n:end])]
        assert pd.to_datetime(train.label_available_at,utc=True).max()<pd.to_datetime(valid.forecast_time_utc,utc=True).min()
        y=valid.y_kronos_wins.to_numpy(float);baseline=float(train.y_kronos_wins.mean())
        rows=valid[['origin_id','session','y_kronos_wins']].copy();rows['fold']=number;rows['baseline']=baseline
        metrics={'baseline':score(y,np.full(len(y),baseline))};fold_models[str(number)]={}
        for name,cols in sets.items():
            model=fit(train[cols].to_numpy(float),train.y_kronos_wins.to_numpy(float));model['columns']=cols
            rows[name]=predict(model,valid[cols].to_numpy(float));metrics[name]=score(y,rows[name].to_numpy())
            fold_models[str(number)][name]=model
        fold_results.append({'fold':number,'train_sessions':days[:n],'validation_sessions':days[n:end],
                             'train_rows':len(train),'validation_rows':len(valid),'metrics':metrics})
        oof.append(rows)
    oof=pd.concat(oof,ignore_index=True);y=oof.y_kronos_wins.to_numpy(float)
    pooled={name:score(y,oof[name].to_numpy(float)) for name in ['baseline',*sets]}
    selected=min(pooled,key=lambda name:(pooled[name]['brier'],len(sets.get(name,[]))))
    model=None
    if selected!='baseline':
        cols=sets[selected];model=fit(may[cols].to_numpy(float),may.y_kronos_wins.to_numpy(float));model['columns']=cols
    frozen={'protocol_sha256':sha(ROOT/'docs/COMPANION_SMALL_V02_PROTOCOL.md'),'inputs':metadata,
            'feature_sets':sets,'fold_models':fold_models,'pooled_may':pooled,'selected':selected,
            'final_model':model,'may_win_frequency':float(may.y_kronos_wins.mean()),'folds':fold_results}
    artifact=out/'frozen_selection.json';text=json.dumps(frozen,indent=2)
    if artifact.exists() and artifact.read_text()!=text:raise ValueError('Frozen selection differs')
    artifact.write_text(text)
    oof.to_csv(out/'may_out_of_fold_predictions.csv',index=False)
    june=tables['june'];assert pd.to_datetime(may.label_available_at,utc=True).max()<pd.to_datetime(june.forecast_time_utc,utc=True).min()
    p0=np.full(len(june),frozen['may_win_frequency']);p=p0 if model is None else predict(model,june[model['columns']].to_numpy(float))
    yj=june.y_kronos_wins.to_numpy(float)
    # Existing validated per-origin errors avoid re-reading or altering forecast outcomes.
    old=pd.read_csv(ROOT/'data/companion_model_v01/june_predictions.csv').set_index('origin_id').loc[june.origin_id]
    assert np.array_equal(old.y_kronos_wins.to_numpy(),yj)
    gate=np.where(p>=.5,old.kronos_error.to_numpy(),old.unchanged_error.to_numpy())
    ledger=june[['origin_id','session','y_kronos_wins']].copy();ledger['selected_probability']=p;ledger['baseline_probability']=p0;ledger['gate_error']=gate
    ledger.to_csv(out/'june_predictions.csv',index=False)
    comparisons={name:interval((oof[name].to_numpy()-y)**2-(oof.baseline.to_numpy()-y)**2,oof.session.to_numpy()) for name in sets}
    report={'scope':'Post-hoc chronological development experiment; June previously used',
            'selected_on_may_only':selected,'exclusions':exclusions,'folds':fold_results,'pooled_may':pooled,
            'may_paired_comparisons':comparisons,'june_selected':score(yj,p),'june_baseline':score(yj,p0),
            'june_paired_brier':interval((p-yj)**2-(p0-yj)**2,june.session.to_numpy()),
            'june_gate_mae':float(gate.mean()),'june_unchanged_mae':float(old.unchanged_error.mean()),
            'june_kronos_mae':float(old.kronos_error.mean()),'selection_sha256':sha(artifact)}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='folds'},indent=2))


if __name__=='__main__':main()
