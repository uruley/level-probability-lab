"""Fixed location bands derived solely from frozen prediction-time levels."""
import math

BANDS=('0_to_0.5R','0.5_to_1R','1_to_2R','over_2R','unknown')
FAMILIES=('hourly_sma','daily_sma','hourly_bb','daily_bb','sma_confluence')


def band(distance):
    if distance is None or not math.isfinite(distance) or distance<0:return 'unknown'
    if distance<=.5:return BANDS[0]
    if distance<=1:return BANDS[1]
    if distance<=2:return BANDS[2]
    return BANDS[3]


def classify(context):
    result={};groups={}
    for timeframe in ['hourly','daily']:
        for kind in ['sma','bb']:
            key=timeframe+'_'+kind
            levels=[v for v in context['levels'] if v['timeframe']==timeframe and v['name'].startswith('SMA' if kind=='sma' else 'BB')]
            valid=len(levels)==(6 if kind=='sma' else 2) and all(v['distance_r'] is not None and math.isfinite(v['distance_r']) for v in levels)
            values=[v['distance_r'] for v in levels] if valid else None
            groups[key]=values
            distance=min(map(abs,values)) if values else None
            result[key+'_distance_r']=distance;result[key+'_band']=band(distance)
    hourly,daily=groups['hourly_sma'],groups['daily_sma']
    distance=min(max(abs(h),abs(d),abs(h-d)) for h in hourly for d in daily) if hourly and daily else None
    result['sma_confluence_distance_r']=distance;result['sma_confluence_band']=band(distance)
    return result
