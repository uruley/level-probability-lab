"""Audit archived context and allowlist point-in-time levels for Jev."""
import hashlib
import json
import math
import pandas as pd
from .jev_compact import build_compact

def context_pair(row, saved, forecast_bytes):
    body = {k:v for k,v in saved.items() if k != 'context_id'}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if digest != saved['context_id'] or hashlib.sha256(forecast_bytes).hexdigest() != saved['forecast_sha256']:
        raise ValueError('Archive hash mismatch')
    if saved['origin'] != row['origin'] or saved['input_sha256'] != row['input_sha256']:
        raise ValueError('Forecast/context mismatch')
    base, _ = build_compact(row)
    ctx = saved['context']; cutoff = pd.Timestamp(base['cutoff'])
    if pd.Timestamp(ctx['as_of']) != cutoff or ctx['reference'] != base['origin_close']:
        raise ValueError('Context cutoff/reference mismatch')
    for frame in ctx['history_evidence'].values():
        for item in frame:
            if pd.Timestamp(item['end']) > cutoff:
                raise ValueError('Future history evidence')
    levels = []
    for level in ctx['levels']:
        stamp, value = level['available_at'], level['value']
        if stamp is not None and pd.Timestamp(stamp) > cutoff:
            raise ValueError('Future level')
        if value is not None and (stamp is None or not math.isfinite(value) or value <= 0):
            raise ValueError('Invalid level availability')
        distance = None if value is None else base['origin_close'] - value
        if distance is not None and not math.isclose(distance, level['distance'], abs_tol=1e-8):
            raise ValueError('Distance mismatch')
        levels.append(dict(name=level['name'], timeframe=level['timeframe'], value=value,
            available_at=stamp, distance_bp=None if distance is None else round(distance/base['origin_close']*10000,4)))
    enriched = dict(base, market_context=dict(status='available', version=ctx['version'],
        convention=ctx['convention'], levels=levels,
        availability_basis='historical completed-bar timestamps; not verified live receipt times'))
    return base, enriched
