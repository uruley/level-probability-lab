"""Fixed, conservative bar-based first-touch response labels."""
import numpy as np
import pandas as pd

def observe(bars, cutoff, level, price, risk):
    cutoff=pd.Timestamp(cutoff)
    if not all(np.isfinite(v) for v in (level,price,risk)) or risk<=0:
        return dict(status='incomplete',reason='invalid frozen level/risk')
    direction=1 if price>level else -1
    lower,upper=level-.1*risk,level+.1*risk
    if lower<=price<=upper:return dict(status='already_inside')
    if bars.bar_start.duplicated().any():return dict(status='incomplete',reason='duplicate minutes')
    frame=bars.set_index('bar_start')
    def valid(t):
        if t not in frame.index:return None
        r=frame.loc[t]
        if not bool(r.feature_eligible) or not bool(r.reconciled):return None
        if not np.isfinite(r[['open','high','low','close','volume','trade_count']].to_numpy(float)).all():return None
        if r.low>min(r.open,r.close) or r.high<max(r.open,r.close) or r.low>r.high:return None
        return r
    touch=None
    for t in pd.date_range(cutoff,periods=60,freq='min'):
        r=valid(t)
        if r is None:return dict(status='incomplete',reason='gap before touch')
        if r.low<=upper and r.high>=lower:
            touch=t;break
        if (direction==1 and r.high<lower) or (direction==-1 and r.low>upper):
            return dict(status='gap_over_zone',time=t.isoformat())
    if touch is None:return dict(status='no_touch')
    r=valid(touch)
    prior=[valid(t) for t in pd.date_range(touch-pd.Timedelta(minutes=20),periods=20,freq='min')]
    mean=float(np.mean([v.volume for v in prior])) if all(v is not None for v in prior) else None
    result=dict(touch=touch.isoformat(),touch_minute_shares=float(r.volume),touch_minute_trades=int(r.trade_count),
        prior20_mean_shares=mean,volume_ratio=float(r.volume/mean) if mean and mean>0 else None,
        rejection_level=level+direction*.5*risk,continuation_level=level-direction*.5*risk)
    for i,t in enumerate(pd.date_range(touch,periods=15,freq='min')):
        r=valid(t)
        if r is None:return dict(result,status='incomplete',reason='gap after touch')
        up=r.high>=level+.5*risk;down=r.low<=level-.5*risk
        if (i==0 and (up or down)) or (up and down):return dict(result,status='ambiguous',resolved_at=t.isoformat())
        if up or down:return dict(result,status='rejection' if (up if direction==1 else down) else 'continuation',resolved_at=t.isoformat())
    return dict(result,status='unresolved')
