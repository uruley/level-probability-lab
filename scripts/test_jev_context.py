"""Approved 80-call paired context experiment; default cached/offline replay."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import dotenv_values
from level_probability_lab.jev_companion import request_real, CLASSES
from level_probability_lab.bull_bear_probability import multiclass_scores, multiclass_losses, paired_session_bootstrap
from freeze_jev_sample import save_frozen

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('kronos_only', 'with_context')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--allow-network',action='store_true')
    parser.add_argument('--june',action='store_true')
    args=parser.parse_args()
    folder=ROOT/('data/jev_context_june_v1' if args.june else 'data/jev_context_sample_v1')
    n=42 if args.june else 40
    manifest=json.loads((folder/'manifest.json').read_text())
    entries=manifest['entries']
    if len(entries)!=n or len({e['origin'] for e in entries})!=n:
        raise ValueError('Unexpected origin count')
    rate=.042/1_000_000
    if 2*n*65536*rate > .25 or manifest['model']!='jev-1.13.0':
        raise ValueError('Budget/model mismatch')
    packages=[]
    for e in entries:
        pair={}
        for arm in ARMS:
            spec=e['packages'][arm]; raw=(folder/spec['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=spec['sha256']: raise ValueError('Package changed')
            pair[arm]=json.loads(raw)
        if {k:v for k,v in pair[ARMS[0]].items() if k!='market_context'} != {k:v for k,v in pair[ARMS[1]].items() if k!='market_context'}:
            raise ValueError('Unpaired inputs')
        packages.append(pair)
    save_frozen(folder/('execution_june.json' if args.june else 'execution_replay_v2.json'),dict(approved_cap_usd=.25,max_requests=2*n,model=manifest['model'],
        bound_usd=2*n*65536*rate,input_rate_per_million=.042,output_free=True,
        pricing_source='https://docs.typesafe.ai/models',pricing_checked='2026-09-23',
        manifest_sha256=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        transport_sha256=hashlib.sha256((ROOT/'src/level_probability_lab/jev_companion.py').read_bytes()).hexdigest()))
    key=dotenv_values(ROOT/'.env').get('TYPESAFE_API_KEY')
    results={a:[] for a in ARMS}; tokens=0
    for i,(e,pair) in enumerate(zip(entries,packages)):
        for arm in ARMS:
            r=request_real(pair[arm],api_key=key,model=manifest['model'],allow_network=args.allow_network,
                cache_dir=folder/'responses'/Path(e['packages'][arm]['file']).stem)
            if r['model']!=manifest['model']: raise ValueError('Response version mismatch')
            results[arm].append(r); tokens+=r['usage']['input_tokens']
        if (i+1)%5==0 or i+1==n: print(f'Validated {2*(i+1)}/{2*n}',flush=True)
    # No outcomes are joined before all responses exist.
    ledger=pd.read_csv(ROOT/'data/kronos_baseline_v1/scores.csv')
    ledger=ledger[(ledger.model=='base') & (ledger.horizon==5)]
    y=[]; audit=[]
    for e,pair in zip(entries,packages):
        match=ledger[ledger.origin==e['origin']]
        if len(match)!=1: raise ValueError('Outcome missing/duplicated')
        actual=float(match.iloc[0].actual); ret=actual/pair[ARMS[0]]['origin_close']-1
        label=0 if ret>.001 else 2 if ret<-.001 else 1
        y.append(label); audit.append(dict(origin=e['origin'],actual=actual,label=CLASSES[label]))
    distributions={a:np.array([[r['scores'][c] for c in CLASSES] for r in results[a]]) for a in ARMS}
    distributions['kronos_base']=np.array([[p[ARMS[0]]['kronos']['final_class_frequencies'][c] for c in CLASSES] for p in packages])
    prior=json.loads((ROOT/'data/bull_bear_truth_v1/baseline_probability_summary_v2.json').read_text())['development_climatology']
    distributions['may_climatology']=np.tile(prior,(n,1))
    distributions['persistence']=np.tile([0,1,0],(n,1))
    metrics={a:dict(zip(['brier','log_loss'],multiclass_scores(y,p))) for a,p in distributions.items()}
    comparisons={a:paired_session_bootstrap([e['origin'][:10] for e in entries],
        multiclass_losses(y,distributions['with_context'])-multiclass_losses(y,p)) for a,p in distributions.items() if a!='with_context'}
    report=dict(n=n,sessions=n//2,metrics=metrics,context_minus=comparisons,
        class_counts=dict(zip(CLASSES,np.bincount(y,minlength=3).tolist())),
        input_tokens=tokens,estimated_cost_usd=tokens*rate,cost_note='published-rate estimate, not receipt',
        missing_responses=0,model=manifest['model'],origins=audit,
        limits=['previously exposed development data; no calibration or promotion',
                'May climatology fixed; analogue unavailable'])
    (folder/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='origins'},indent=2))

if __name__=='__main__': main()
