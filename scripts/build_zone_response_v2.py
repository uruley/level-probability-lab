"""Expanded fixed June study. Local audited files only."""
import json
from collections import Counter, defaultdict
import pandas as pd
from build_zone_response import ROOT, digest
from freeze_jev_sample import save_frozen
from level_probability_lab.calendar import session_schedule, expected_regular_minutes
from level_probability_lab.zone_levels import levels
from level_probability_lab.zone_response import observe


def main():
    source = ROOT/'data/trades_study/trade_features_may_june.parquet'
    audit = json.loads((source.parent/'trade_feature_audit.json').read_text())
    if not audit['accepted'] or digest(source) != audit['features_sha256']:
        raise ValueError('Trade audit failed')
    bars = pd.read_parquet(source)
    schedule = session_schedule('2026-05-01', '2026-06-30')
    grid = expected_regular_minutes(schedule)
    contexts = ROOT/'data/location_evaluation_v1/prediction_contexts.jsonl'
    origins = {}
    import hashlib
    for line in contexts.open():
        r = json.loads(line)
        if not r['date'].startswith('2026-06'):
            continue
        body = {k:v for k,v in r.items() if k != 'context_id'}
        if hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest() != r['context_id']:
            raise ValueError('Context hash mismatch')
        origins.setdefault((r['date'],r['context']['as_of']), r)
    print(f'Freezing {len(origins)} June origins', flush=True)
    indexed = bars.set_index('bar_start')
    days = {d:g for d,g in bars.groupby(bars.bar_start.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d'))}
    frozen = []
    for (date,cutoff),r in sorted(origins.items()):
        c = r['context']
        opening = schedule.loc[pd.Timestamp(date)].market_open
        values = levels(indexed,grid,opening,pd.Timestamp(cutoff))
        for v in c['levels']:
            if (v['timeframe']=='daily' and v['name'] in ('Previous high','Previous low')) or (v['timeframe']=='hourly' and v['name']=='SMA 20'):
                values[v['timeframe']+' '+v['name']] = v['value'] if v['available_at'] and pd.Timestamp(v['available_at']) <= pd.Timestamp(cutoff) else None
        for name,value in values.items():
            frozen.append(dict(id=cutoff+'|'+name,date=date,name=name,cutoff=cutoff,
                               level=value,price=c['reference'],risk=c['risk'],context_id=r['context_id']))
    out = ROOT/'data/zone_response_v2'; out.mkdir(exist_ok=True)
    save_frozen(out/'inputs.json',frozen)
    save_frozen(out/'manifest.json',dict(protocol_sha256=digest(ROOT/'docs/ZONE_RESPONSE_V2.md'),
        trade_sha256=digest(source),context_sha256=digest(contexts),
        code_sha256={p:digest(ROOT/p) for p in ['scripts/build_zone_response_v2.py','src/level_probability_lab/zone_levels.py','src/level_probability_lab/zone_response.py']}))
    print(f'Scoring {len(frozen)} frozen candidates', flush=True)
    results=[]; grouped=defaultdict(Counter)
    for event in frozen:
        day=days[event['date']]
        result = dict(status='unavailable') if event['level'] is None else observe(day,event['cutoff'],event['level'],event['price'],event['risk'])
        results.append(dict(id=event['id'],**result)); grouped[event['name']][result['status']]+=1
    save_frozen(out/'outcomes.json',results)
    summary=dict(origins=len(origins),sessions=len({d for d,t in origins}),candidates=len(frozen),by_level=dict(grouped))
    save_frozen(out/'summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
