"""Read-only model diagnosis on used May/June data; no fitting or selection."""
import json
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT
from level_probability_lab.companion_logistic import predict


def main():
    root=ROOT/'data/companion_model_v01';source=ROOT/'data/companion_v02/may_june'
    frozen=json.loads((root/'frozen_model.json').read_text())
    out=root/'diagnosis';out.mkdir(exist_ok=True)
    datasets={};results={};sessions=[]
    for month in ['may','june']:
        x=pd.read_parquet(source/f'features_{month}.parquet')
        labels=pd.read_parquet(source/f'labels_{month}.parquet')
        x=x.merge(labels,on='origin_id',validate='one_to_one')
        x=x.loc[x.label_eligible & ~x.tie_flag & x.ts_block_available & x.candle_features_complete].copy()
        for day in range(2,6):x[f'dow_{day}']=(x.dow_ny==day).astype(float)
        datasets[month]=x
        y=x.y_kronos_wins.to_numpy(float);p0=frozen['train_win_frequency']
        results[month]={'rows':len(x),'win_rate':float(y.mean()),'constant_brier':float(np.mean((p0-y)**2)),'models':{}}
        for name,m in frozen['models'].items():
            p=predict(m,x[m['columns']].to_numpy(float))
            e=(p-y)**2;delta=e-(p0-y)**2
            # Descriptive calibration slope of outcome on probability; no model changes.
            variance=float(np.var(p))
            slope=float(np.mean((p-p.mean())*(y-y.mean()))/variance) if variance else None
            bins=[]
            for lo,hi in [(0,.4),(.4,.5),(.5,.6),(.6,1.000001)]:
                mask=(p>=lo)&(p<hi)
                bins.append({'range':[lo,min(hi,1)],'n':int(mask.sum()),'mean_p':float(p[mask].mean()) if mask.any() else None,'actual_win_rate':float(y[mask].mean()) if mask.any() else None})
            results[month]['models'][name]={'brier':float(e.mean()),'excess_brier':float(delta.mean()),
                'mean_probability':float(p.mean()),'probability_std':float(p.std()),'linear_calibration_slope':slope,
                'gated_to_kronos_fraction':float(np.mean(p>=.5)),'bins':bins,
                'mean_bias_squared':float((p.mean()-y.mean())**2),
                'probability_variance':variance,'twice_probability_outcome_covariance':float(2*np.mean((p-p.mean())*(y-y.mean())))}
            daily=pd.DataFrame({'date':x.forecast_time_utc.str[:10].to_numpy(),'excess_brier':delta,'p':p,'y':y}).groupby('date').agg(n=('y','size'),excess_brier=('excess_brier','mean'),mean_p=('p','mean'),win_rate=('y','mean')).reset_index()
            daily['month']=month;daily['model']=name;sessions.extend(daily.to_dict('records'))
            if month=='june':
                totals=daily.excess_brier*daily.n
                leave=(totals.sum()-totals)/(daily.n.sum()-daily.n)
                results[month]['models'][name]['sessions_worse_than_constant']=int((daily.excess_brier>0).sum())
                results[month]['models'][name]['leave_one_session_out_excess_brier_range']=[float(leave.min()),float(leave.max())]
    shifts=[];coefficients=[];families=[]
    for name,m in frozen['models'].items():
        cols=m['columns'];a=datasets['may'][cols].to_numpy(float);b=datasets['june'][cols].to_numpy(float)
        keep=np.array(m['keep']);mean=np.array(m['mean']);std=np.array(m['std'])
        z=(b[:,keep]-mean[keep])/std[keep];beta=np.array(m['beta'])[1:]
        kept=np.array(cols)[keep]
        for j,c in enumerate(kept):
            orig=cols.index(c)
            shifts.append({'model':name,'feature':c,'mean_shift_in_may_sd':float(z[:,j].mean()),'june_to_may_sd_ratio':float(z[:,j].std()),'june_outside_may_range_fraction':float(np.mean((b[:,orig]<a[:,orig].min())|(b[:,orig]>a[:,orig].max())))})
            coefficients.append({'model':name,'feature':c,'coefficient_per_may_sd':float(beta[j]),'june_logit_contribution_std':float((z[:,j]*beta[j]).std())})
        # Fixed-model diagnostic only: set each family to its May mean (z=0).
        # This can create unrealistic combinations; it is not retraining/causal attribution.
        def family(c):
            if c.startswith('ts_'):return 'trades'
            if c.startswith('k_'):return 'kronos'
            if c.startswith(('tod_','is_','dow_')):return 'clock'
            if 'prev_' in c and not c.startswith('m5'):return 'previous_session'
            if c.startswith(('m5_','h60_')):return 'higher_timeframe'
            return 'other_candle_indicators'
        from level_probability_lab.companion_logistic import sigmoid
        y=datasets['june'].y_kronos_wins.to_numpy(float)
        base=np.mean((sigmoid(m['beta'][0]+z@beta)-y)**2)
        for group in sorted({family(c) for c in kept}):
            mask=np.array([family(c)==group for c in kept]);modified=z.copy();modified[:,mask]=0
            error=np.mean((sigmoid(m['beta'][0]+modified@beta)-y)**2)
            families.append({'model':name,'family_set_to_may_mean':group,'brier_change':float(error-base)})
    pd.DataFrame(sessions).to_csv(out/'session_diagnostics.csv',index=False)
    pd.DataFrame(shifts).to_csv(out/'feature_shifts.csv',index=False)
    pd.DataFrame(coefficients).to_csv(out/'coefficients.csv',index=False)
    report={'scope':'Post-hoc May/June diagnosis only; no model changes; family substitutions are exploratory',
            'periods':results,'family_sensitivity':families}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print('Largest shifts:',pd.DataFrame(shifts).query("model=='trades'").assign(magnitude=lambda d:d.mean_shift_in_may_sd.abs()).nlargest(6,'magnitude').to_dict('records'))
    print('Largest coefficients:',pd.DataFrame(coefficients).query("model=='trades'").assign(magnitude=lambda d:d.coefficient_per_may_sd.abs()).nlargest(6,'magnitude').to_dict('records'))


if __name__=='__main__':main()
