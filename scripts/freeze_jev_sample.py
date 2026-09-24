"""Freeze ten chronological May packages. Never reads outcomes or calls an API."""
import hashlib
import json
from pathlib import Path
from level_probability_lab.jev_compact import build_compact

ROOT = Path(__file__).resolve().parents[1]


def save_frozen(path, value):
    encoded = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f'Frozen artifact changed: {path.name}')
    else:
        with path.open('xb') as f:
            f.write(encoded)


def main():
    source = ROOT / 'data/kronos_baseline_v1/forecasts/base'
    selected = {}
    # Selection uses filenames only, excluding the already examined May 1 pilot.
    for path in sorted(source.glob('202605*.json')):
        day = path.name[:8]
        if day == '20260501':
            continue
        selected.setdefault(day, path)
    paths = list(selected.values())[:10]
    if len(paths) != 10:
        raise ValueError('Ten sessions required; do not substitute silently')
    prepared = []
    for path in paths:
        raw = path.read_bytes()
        row = json.loads(raw)
        package, digest = build_compact(row)
        prepared.append((path, package, digest, hashlib.sha256(raw).hexdigest()))
    output = ROOT / 'data/jev_sample_v1'
    output.mkdir(exist_ok=True)
    entries = []
    for path, package, digest, source_hash in prepared:
        save_frozen(output / path.name, package)
        entries.append(dict(file=path.name, cutoff=package['cutoff'],
            source=str(path.relative_to(ROOT)), source_sha256=source_hash,
            package_sha256=digest))
    manifest = dict(version='jev_sample_v1', selection='earliest archived Base origin on first ten May sessions after May 1',
        purpose='development feasibility pilot; not an independent skill test',
        model='jev-1.13.0', schema='jev_compact_v1', entries=entries,
        max_requests=10, proposed_spending_cap_usd=.25, approved_spending_cap_usd=0,
        network_enabled=False, pricing_verified=False,
        budget_policy='No requests until pricing and enforceable local cost bound are verified and this batch is approved. No automatic retries.',
        comparisons=['Kronos Base', 'May class frequency (in-sample descriptive)', 'neutral persistence'],
        analogue_status='requires compatible same-origin distributions; unavailable is not a synthetic baseline',
        scoring='freeze responses before joining outcomes; raw multiclass Brier and epsilon=1e-6 log loss; paired session bootstrap descriptive only',
        calibration='none; no tuning on ten examples',
        code_sha256=hashlib.sha256((ROOT / 'src/level_probability_lab/jev_compact.py').read_bytes()).hexdigest())
    save_frozen(output / 'manifest.json', manifest)
    print(json.dumps(dict(count=len(entries), first=entries[0]['cutoff'], last=entries[-1]['cutoff'],
        network_calls=0, manifest=str(output / 'manifest.json')), indent=2))


if __name__ == '__main__':
    main()
