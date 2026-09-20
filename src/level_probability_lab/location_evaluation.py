"""Offline first-touch evaluation and session-block uncertainty."""
import numpy as np
import pandas as pd


def score_path(future, reference, risk, direction, ratio, minutes):
    if direction==0 or not np.isfinite(risk) or risk<=0:
        return {'status':'no_setup','outcome':None,'minutes':None}
    target=reference+direction*ratio*risk;stop=reference-direction*risk
    for i,bar in enumerate(future[:minutes]):
        if not np.isfinite(bar).all():
            return {'status':'incomplete','outcome':None,'minutes':None}
        high,low=bar[1:3]
        a=high>=target if direction==1 else low<=target
        b=low<=stop if direction==1 else high>=stop
        if a or b:return {'status':'complete','outcome':'ambiguous' if a and b else 'target_first' if a else 'stop_first','minutes':i+1}
    if len(future)<minutes:return {'status':'incomplete','outcome':None,'minutes':None}
    return {'status':'complete','outcome':'neither','minutes':minutes}


def interval(frame, numerator, denominator, seed=20260919, dates=None):
    grouped=frame.groupby('date')[[numerator,denominator]].sum()
    if dates is not None:grouped=grouped.reindex(sorted(dates),fill_value=0)
    contributing=int((grouped[denominator]>0).sum())
    total=grouped.sum();point=float(total[numerator]/total[denominator]) if total[denominator]>0 else None
    if contributing<2:return dict(value=point,ci95=None,sessions=contributing,valid_draws=0)
    a=grouped.to_numpy(float);rng=np.random.default_rng(seed)
    draws=a[rng.integers(0,len(a),size=(2000,len(a)))].sum(axis=1)
    good=draws[:,1]>0;values=draws[good,0]/draws[good,1]
    return dict(value=point,ci95=np.quantile(values,[.025,.975]).tolist() if good.sum()>=1900 else None,sessions=contributing,valid_draws=int(good.sum()))


def contrast(frame, numerator, denominator):
    dates=sorted(frame.date.unique());arrays=[];counts=[]
    for group in ['confluence','no_confluence']:
        g=frame.loc[frame.group==group].groupby('date')[[numerator,denominator]].sum().reindex(dates,fill_value=0)
        arrays.append(g.to_numpy(float));counts.append(int((g[denominator]>0).sum()))
    def diff(a,b):return a[0]/a[1]-b[0]/b[1] if a[1]>0 and b[1]>0 else None
    point=diff(arrays[0].sum(axis=0),arrays[1].sum(axis=0))
    if min(counts)<2:return dict(value=point,ci95=None,sessions=counts,valid_draws=0)
    idx=np.random.default_rng(20260919).integers(0,len(dates),size=(2000,len(dates)))
    a,b=[v[idx].sum(axis=1) for v in arrays];good=(a[:,1]>0)&(b[:,1]>0)
    values=a[good,0]/a[good,1]-b[good,0]/b[good,1]
    return dict(value=point,ci95=np.quantile(values,[.025,.975]).tolist() if good.sum()>=1900 else None,sessions=counts,valid_draws=int(good.sum()))
