"""Five elapsed-minute extremes, distinct from pointwise close dispersion."""
import numpy as np
import pandas as pd


def forecast_range(paths, reference):
    a=np.asarray(paths,float)
    valid=np.isfinite(a).all(axis=(1,2)) & (a[:,:,1]>=a[:,:,[0,2,3]].max(axis=2)).all(axis=1) & (a[:,:,2]<=a[:,:,[0,1,3]].min(axis=2)).all(axis=1)
    a=a[valid]
    result={'reference_close':float(reference),'valid_paths':int(valid.sum()),'excluded_paths':int((~valid).sum())}
    values={} if not len(a) else {'high':a[:,:,1].max(axis=1),'low':a[:,:,2].min(axis=1)}
    if len(a):
        values.update(upside=np.maximum(0,values['high']-reference),downside=np.maximum(0,reference-values['low']))
    for key in ['high','low','upside','downside']:
        result[key]=None if not len(a) else {'median':float(np.median(values[key])), 'p10':float(np.quantile(values[key],.1)), 'p90':float(np.quantile(values[key],.9))}
    return result


def observed_range(predicted, targets, revealed):
    stamps=pd.to_datetime(targets,utc=True)
    seen=revealed.loc[revealed.bar_start.isin(stamps)].sort_values('bar_start')
    finished=revealed.iloc[-1].bar_end>=stamps[-1]+pd.Timedelta(minutes=1)
    complete=finished and len(seen)==5
    result={'status':'complete' if complete else 'incomplete' if finished else 'pending', 'observed_minutes':len(seen)}
    high=float(seen.high.max()) if len(seen) else None
    low=float(seen.low.min()) if len(seen) else None
    reference=predicted['reference_close']
    values={'high':high,'low':low,'upside':None if high is None else max(0,high-reference),'downside':None if low is None else max(0,reference-low)}
    result['actual']=values
    result['absolute_errors']={key:abs(predicted[key]['median']-value) if complete and predicted[key] is not None else None for key,value in values.items()}
    return result
