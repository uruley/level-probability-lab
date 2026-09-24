"""Freeze forty paired contexts without reading scores or contacting Jev."""
import hashlib
import argparse
import json
from pathlib import Path
from collections import defaultdict
from level_probability_lab.jev_context import context_pair
from freeze_jev_sample import save_frozen

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--june',action='store_true')
    june=parser.parse_args().june
    month='2026-06' if june else '2026-05'
    archive = ROOT / 'data/location_evaluation_v1/prediction_contexts.jsonl'
    contexts = {}
    with archive.open() as f:
        for line in f:
            item = json.loads(line)
            if item['date'].startswith(month):
                if item['origin'] in contexts: raise ValueError('Duplicate origin')
                contexts[item['origin']] = item
    days = defaultdict(list)
    for path in sorted((ROOT/'data/kronos_baseline_v1/forecasts/base').glob(month.replace('-','')+'*.json')):
        days[path.name[:8]].append(path)
    if len(days) != (21 if june else 20): raise ValueError('Unexpected session count')
    prepared = []
    for day, paths in sorted(days.items()):
        if len(paths) < 28: raise ValueError('Insufficient origins')
        for path in (paths[0], paths[27]):
            raw = path.read_bytes(); row = json.loads(raw)
            saved = contexts[row['origin']]
            base, enriched = context_pair(row, saved, raw)
            prepared.append((path, saved, base, enriched))
    out = ROOT/('data/jev_context_june_v1' if june else 'data/jev_context_sample_v1'); out.mkdir(exist_ok=True)
    entries=[]
    for path, saved, base, enriched in prepared:
        files={}
        for name, package in [('kronos_only',base),('with_context',enriched)]:
            file=f'{path.stem}_{name}.json'; save_frozen(out/file, package)
            files[name]=dict(file=file,sha256=hashlib.sha256((out/file).read_bytes()).hexdigest())
        entries.append(dict(origin=saved['origin'], context_id=saved['context_id'],
            forecast_sha256=saved['forecast_sha256'],packages=files))
    manifest=dict(version='jev_context_sample_v1',entries=entries,
        selection='May 20 sessions; zero-based archived origins 0 and 27 each; no outcome selection',
        max_requests=80,model='jev-1.13.0',proposed_cap_usd=.25,approved_cap_usd=0,network_enabled=False,
        pricing_note='80 full-context requests at previously verified rate would be $0.22020096; reverify before run',
        comparison='paired Jev context vs Jev no-context vs Kronos; freeze responses before outcomes',
        limits=['previously explored development data, not untouched validation','bar timestamps do not prove live receipt availability','no order flow; no calibration; analogue not available'],
        context_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        builder_sha256=hashlib.sha256((ROOT/'src/level_probability_lab/jev_context.py').read_bytes()).hexdigest())
    if june:
        manifest.update(version='jev_context_june_v1',
            selection='June 21 sessions; zero-based archived origins 0 and 27 each; no outcome selection',
            max_requests=84,pricing_note='84 full-context requests at verified rate bound $0.231211008; reverify before run')
    save_frozen(out/'manifest.json',manifest)
    print(json.dumps(dict(origins=len(entries),packages=2*len(entries),network_calls=0,
        missing_levels=sum(v['value'] is None for _,_,_,p in prepared for v in p['market_context']['levels']),
        min_date=entries[0]['origin'],max_date=entries[-1]['origin']),indent=2))

if __name__ == '__main__': main()
