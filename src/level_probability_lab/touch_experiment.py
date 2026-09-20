"""Frozen five-minute target/stop touch research; never execution simulation."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

OUTCOMES = ('target_first', 'stop_first', 'neither', 'ambiguous')


def first_touch(candles, target, stop, direction):
    for candle in candles:
        high, low = candle[1], candle[2]
        target_hit = high >= target if direction == 1 else low <= target
        stop_hit = low <= stop if direction == 1 else high >= stop
        if target_hit and stop_hit:
            return 'ambiguous'
        if target_hit:
            return 'target_first'
        if stop_hit:
            return 'stop_first'
    return 'neither'


def setup(row):
    bars = row['input_window']
    paths = np.asarray(row['sampled_paths'], float)
    reference = float(bars[-1]['close'])
    difference = float(np.median(paths[:, -1, 3])) - reference
    direction = int(np.sign(difference))
    result = {'version': 'atr14-touch-v1', 'reference': reference,
              'direction': 'up' if direction == 1 else 'down' if direction == -1 else 'neutral',
              'atr_convention': 'Wilder14 seeded from frozen input window; first TR=high-low',
              'status': 'ready', 'risk': None, 'setups': []}
    if len(bars) < 14:
        result['status'] = 'insufficient_lookback'
        return result
    tr = [max(b['high']-b['low'], abs(b['high']-bars[i-1]['close']), abs(b['low']-bars[i-1]['close']))
          if i else b['high']-b['low'] for i,b in enumerate(bars)]
    risk = float(np.mean(tr[:14]))
    for v in tr[14:]: risk = (risk*13+v)/14
    if not np.isfinite(risk) or risk <= 0:
        result['status'] = 'degenerate_volatility'
        return result
    result['risk'] = risk
    if direction == 0:
        result['status'] = 'neutral'
        return result
    valid = np.isfinite(paths).all(axis=(1,2)) & (paths[:,:,1]>=paths[:,:,[0,2,3]].max(axis=2)).all(axis=1) & (paths[:,:,2]<=paths[:,:,[0,1,3]].min(axis=2)).all(axis=1)
    result.update(valid_paths=int(valid.sum()), excluded_paths=int((~valid).sum()))
    for ratio in [1,2,3]:
        target,stop = reference+direction*ratio*risk,reference-direction*risk
        counts = {k:0 for k in OUTCOMES}
        for path in paths[valid]: counts[first_touch(path,target,stop,direction)] += 1
        result['setups'].append({'ratio':ratio,'target':target,'stop':stop,'path_counts':counts,
                                'path_percentages':{k:100*v/int(valid.sum()) if valid.any() else None for k,v in counts.items()}})
    return result


def observe(frozen, targets, revealed, extended=False):
    """Resolve immediately, but never infer first touch across a missing minute."""
    if frozen['status'] != 'ready': return []
    start = pd.Timestamp(targets[0])
    deadline = pd.Timestamp(targets[-1]) + pd.Timedelta(minutes=1)
    if extended:
        deadline = min(start + pd.Timedelta(minutes=60), revealed.iloc[0].session_close)
    clock = revealed.iloc[-1].bar_end
    stamps = pd.date_range(start, min(clock, deadline), freq='min', inclusive='left') if clock > start else []
    selected = revealed.set_index('bar_start')
    direction = 1 if frozen['direction']=='up' else -1
    results = []
    for s in frozen['setups']:
        result = {'ratio': s['ratio'], 'status': 'open' if extended else 'pending',
                  'outcome': None, 'resolved_at': None, 'minutes_to_resolution': None,
                  'deadline': deadline.isoformat(), 'evaluation_version': 'touch-v2'}
        for stamp in stamps:
            if stamp not in selected.index:
                result['status'] = 'incomplete'
                break
            bar = selected.loc[stamp]
            outcome = first_touch([[bar.open,bar.high,bar.low,bar.close]],s['target'],s['stop'],direction)
            if outcome != 'neither':
                end = stamp + pd.Timedelta(minutes=1)
                result.update(status='complete', outcome=outcome, resolved_at=end.isoformat(),
                              minutes_to_resolution=int((end-start).total_seconds()/60))
                break
        else:
            if clock >= deadline:
                result.update(status='complete', outcome='expired' if extended else 'neither',
                              resolved_at=deadline.isoformat(),
                              minutes_to_resolution=int((deadline-start).total_seconds()/60))
        results.append(result)
    return results


def summary(forecasts, extended=False):
    outcomes = ('target_first','stop_first','expired','ambiguous') if extended else OUTCOMES
    pending = 'open' if extended else 'pending'
    results=[]
    for ratio in [1,2,3]:
        counts={k:0 for k in (*outcomes,pending,'incomplete','no_setup')}
        for f in forecasts:
            values = f['extended_touch_outcomes' if extended else 'touch_outcomes']
            if not values: counts['no_setup']+=1;continue
            value=next(v for v in values if v['ratio']==ratio)
            counts[value['outcome'] if value['status']=='complete' else value['status']]+=1
        completed=sum(counts[k] for k in outcomes)
        results.append({'ratio':ratio,'completed':completed,'counts':counts,
                        'percentages':{k:100*counts[k]/completed if completed else None for k in outcomes}})
    return results


def save_setup(row, output):
    payload={'forecast_id':row['forecast_id'],'targets':row['target_timestamps'],'setup':setup(row)}
    text=json.dumps(payload,sort_keys=True,allow_nan=False)
    directory=Path(output)/'touch_setups';directory.mkdir(parents=True,exist_ok=True)
    path=directory/(hashlib.sha256(text.encode()).hexdigest()+'.json')
    if not path.exists():
        with path.open('x',encoding='utf-8') as f:f.write(text)
