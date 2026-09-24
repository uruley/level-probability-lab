"""Offline May candidate-zone pilot with a standalone visual ledger."""
import hashlib
import html
import json
from pathlib import Path
import pandas as pd
from level_probability_lab.zone_response import observe
from freeze_jev_sample import save_frozen

ROOT=Path(__file__).resolve().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    trade=ROOT/'data/trades_study/trade_features_may_june.parquet'
    audit=json.loads((trade.parent/'trade_feature_audit.json').read_text())
    if not audit['accepted'] or digest(trade)!=audit['features_sha256']:raise ValueError('Trade audit failed')
    contexts=ROOT/'data/location_evaluation_v1/prediction_contexts.jsonl'
    first={}
    for line in contexts.open():
        r=json.loads(line)
        if r['date'].startswith('2026-05') and (r['date'] not in first or r['origin']<first[r['date']]['origin']):first[r['date']]=r
    if len(first)!=20:raise ValueError('Expected twenty May sessions')
    frozen=[]
    for date,r in sorted(first.items()):
        c=r['context']; body={k:v for k,v in r.items() if k!='context_id'}
        if hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()!=r['context_id']:raise ValueError('Context hash mismatch')
        for v in c['levels']:
            if (v['timeframe']=='daily' and v['name'] in ('Previous high','Previous low')) or (v['timeframe']=='hourly' and v['name']=='SMA 20'):
                if v['value'] is None or pd.Timestamp(v['available_at'])>pd.Timestamp(c['as_of']):raise ValueError('Level unavailable')
                frozen.append(dict(id=date+'|'+v['timeframe']+'|'+v['name'],date=date,name=v['timeframe']+' '+v['name'],
                    cutoff=c['as_of'],level=v['value'],price=c['reference'],risk=c['risk'],context_id=r['context_id']))
    out=ROOT/'data/zone_response_v1';out.mkdir(exist_ok=True)
    save_frozen(out/'inputs.json',frozen)
    save_frozen(out/'manifest.json',dict(protocol_sha256=digest(ROOT/'docs/ZONE_RESPONSE_V1.md'),
        trade_sha256=digest(trade),context_sha256=digest(contexts),code_sha256=digest(ROOT/'src/level_probability_lab/zone_response.py'),
        scope='May only; Nasdaq traded volume per whole minute; no paid calls'))
    bars=pd.read_parquet(trade,filters=[('bar_start','>=',pd.Timestamp('2026-05-01',tz='UTC')),('bar_start','<',pd.Timestamp('2026-06-01',tz='UTC'))])
    results=[];markup=[]
    for event in frozen:
        day=bars[bars.bar_start.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')==event['date']]
        result=observe(day,event['cutoff'],event['level'],event['price'],event['risk'])
        results.append(dict(id=event['id'],**result))
        series=day[(day.bar_start>=pd.Timestamp(event['cutoff'])) & (day.bar_start<pd.Timestamp(event['cutoff'])+pd.Timedelta(minutes=75))]
        prices=series.close.tolist();level=event['level'];risk=event['risk']
        lo=min(prices+[level-risk]);hi=max(prices+[level+risk]);y=lambda p: 115-(p-lo)/(hi-lo)*105
        points=' '.join(f'{10+i*460/max(1,len(prices)-1):.1f},{y(p):.1f}' for i,p in enumerate(prices))
        lines=''.join(f'<line x1="10" x2="470" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="{color}" stroke-dasharray="4 4"/>' for p,color in [(level,'#ffd166'),(level+.5*risk,'#8cd9ba'),(level-.5*risk,'#f39494')])
        svg=f'<svg viewBox="0 0 480 125" role="img" aria-label="Observed minute closes and frozen level barriers">{lines}<polyline points="{points}" stroke="#79bfff" fill="none"/></svg>'
        vol=result.get('touch_minute_shares');ratio=result.get('volume_ratio')
        markup.append(f'<tr><td>{event["date"]}<br>{html.escape(event["name"])}<br>${level:.3f}</td><td>{result["status"]}<br>{html.escape(result.get("touch",""))}</td><td>{f"{vol:,.0f} shares" if vol is not None else "—"}<br>{f"{ratio:.2f}× prior 20-minute mean" if ratio is not None else "—"}</td><td>{svg}</td></tr>')
    save_frozen(out/'outcomes.json',results)
    counts=pd.Series([r['status'] for r in results]).value_counts().to_dict()
    (out/'summary.json').write_text(json.dumps(counts,indent=2))
    page='''<!doctype html><meta charset="utf-8"><title>Candidate area response ledger</title><style>body{background:#101923;color:#e6edf3;font:16px system-ui;margin:32px}table{width:100%;border-collapse:collapse}td,th{padding:12px;text-align:left;border-bottom:1px solid #345}td:last-child{width:42%}svg{width:100%}p{max-width:1000px;color:#bdd0de}</style><h1>Candidate areas · observed response</h1><p>Historical May pilot — not measured resting liquidity, a trade signal or a probability estimate. All 60 candidates shown. Zone ±0.1R; response barriers ±0.5R. Touch-minute volume is Nasdaq-only whole-minute volume, not volume inside the zone.</p><p>Blue: actual minute closes after cutoff. Gold: frozen candidate level. Green/red: upper/lower barriers (not buy/sell signals). Charts show the full 75-minute observation window; outcome timing may end earlier. OHLC touch order is conservatively ambiguous.</p>'''
    page+='<p>'+html.escape(json.dumps(counts))+'</p><table><tr><th>Frozen area</th><th>Observed response / touch UTC</th><th>Executed volume</th><th>Actual price path</th></tr>'+''.join(markup)+'</table>'
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(candidates=len(results),counts=counts,view=str(out/'index.html')),indent=2))

if __name__=='__main__':main()
