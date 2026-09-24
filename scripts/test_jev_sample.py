"""Run the approved ten-origin compact pilot, then score saved answers."""
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-network', action='store_true')
    args = parser.parse_args()
    folder = ROOT / 'data/jev_sample_v1'
    manifest = json.loads((folder / 'manifest.json').read_text())
    entries = manifest['entries']
    if len(entries) != 10 or len({e['file'] for e in entries}) != 10:
        raise ValueError('Expected exactly ten distinct frozen entries')
    # Whole model context charged at published input rate is a conservative bound.
    rate = .042 / 1_000_000
    bound = len(entries) * 65536 * rate
    if bound > .25 or manifest['model'] != 'jev-1.13.0':
        raise ValueError('Budget or model mismatch')
    packages = []
    for e in entries:
        p = json.loads((folder / e['file']).read_text())
        raw = json.dumps(p, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if hashlib.sha256(raw).hexdigest() != e['package_sha256']:
            raise ValueError('Package changed')
        if hashlib.sha256((ROOT / e['source']).read_bytes()).hexdigest() != e['source_sha256']:
            raise ValueError('Source changed')
        packages.append(p)
    config = dict(model=manifest['model'], max_requests=10, approved_cap_usd=.25,
        published_usd_per_million_input_tokens=.042, output_tokens_free=True,
        conservative_batch_bound_usd=bound, pricing_source='https://docs.typesafe.ai/models',
        pricing_checked='2026-09-23', manifest_sha256=hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest(),
        transport_sha256=hashlib.sha256((ROOT / 'src/level_probability_lab/jev_companion.py').read_bytes()).hexdigest())
    save_frozen(folder / 'execution.json', config)
    key = dotenv_values(ROOT / '.env').get('TYPESAFE_API_KEY')
    results = []
    for e, p in zip(entries, packages):
        r = request_real(p, api_key=key, model=manifest['model'],
            allow_network=args.allow_network, cache_dir=folder / 'responses' / Path(e['file']).stem)
        if r['model'] != manifest['model']:
            raise ValueError('Response model mismatch; stopping')
        results.append(r)
        print(f'Validated {len(results)}/10', flush=True)
    # Outcomes are read only after all ten responses have been frozen.
    ledger = pd.read_csv(ROOT / 'data/kronos_baseline_v1/scores.csv')
    ledger = ledger[(ledger.model == 'base') & (ledger.horizon == 5)]
    y, kronos, per_origin = [], [], []
    for e, p, r in zip(entries, packages, results):
        source = json.loads((ROOT / e['source']).read_text())
        match = ledger[ledger.origin == source['origin']]
        if len(match) != 1:
            raise ValueError('Outcome is missing or duplicated')
        actual = float(match.iloc[0].actual)
        ret = actual / p['origin_close'] - 1
        label = 0 if ret > .001 else 2 if ret < -.001 else 1
        y.append(label)
        kronos.append([p['kronos']['final_class_frequencies'][c] for c in CLASSES])
        per_origin.append(dict(cutoff=e['cutoff'], actual_close=actual, label=CLASSES[label],
            jev_scores=r['scores'], jev_raw_scores=r['raw_scores']))
    prior = json.loads((ROOT / 'data/bull_bear_truth_v1/baseline_probability_summary_v2.json').read_text())['development_climatology']
    distributions = dict(jev=np.array([[r['scores'][c] for c in CLASSES] for r in results]),
        kronos_base=np.array(kronos), may_climatology=np.tile(prior, (10,1)), persistence=np.tile([0,1,0], (10,1)))
    metrics = {name: dict(zip(['brier','log_loss'], multiclass_scores(y,p))) for name,p in distributions.items()}
    differences = {name: paired_session_bootstrap([e['cutoff'][:10] for e in entries],
        multiclass_losses(y, distributions['jev']) - multiclass_losses(y,p))
        for name,p in distributions.items() if name != 'jev'}
    tokens = sum(r['usage']['input_tokens'] for r in results)
    report = dict(n=10, metrics=metrics, jev_minus_baseline=differences,
        class_counts=dict(zip(CLASSES,np.bincount(y,minlength=3).tolist())),
        input_tokens=tokens, estimated_cost_usd=tokens * rate,
        cost_note='published-rate estimate, not a billing receipt',
        limitations=['ten previously explored development origins; no calibration or skill claim',
        'May climatology in-sample descriptive; analogue unavailable'], origins=per_origin)
    (folder / 'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('origins','jev_minus_baseline')},indent=2))

if __name__ == '__main__':
    main()
