"""No network or key access. Prepare the same May 1 origin used in the pilot."""
import json
from pathlib import Path
from level_probability_lab.jev_compact import build_compact

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'data/kronos_baseline_v1/forecasts/base/20260501T152900Z.json'
row = json.loads(source.read_text())
package, digest = build_compact(row)
output = ROOT / 'data/jev_compact_v1'
output.mkdir(exist_ok=True)
encoded = json.dumps(package, sort_keys=True, separators=(',', ':'))
(output / 'package.json').write_text(encoded)
prior = next((ROOT / 'data/jev_pilot_v1').glob('*.request.json'))
old = json.loads(prior.read_text())['state']
old_bytes = len(json.dumps(old, sort_keys=True, separators=(',', ':')).encode())
report = dict(source=str(source.relative_to(ROOT)), package_sha256=digest,
    compact_bytes=len(encoded.encode()), prior_state_bytes=old_bytes,
    reduction_percent=100 * (1 - len(encoded.encode()) / old_bytes),
    tokens='not measured; byte reduction is not a token or dollar quote',
    network_calls=0, context='unavailable; not reconstructed or invented')
(output / 'manifest.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
