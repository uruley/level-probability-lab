"""One archived May origin, one durable request reservation, no retries."""
import argparse
import json
from pathlib import Path
import numpy as np
from dotenv import dotenv_values
from level_probability_lab.jev_companion import build_package, request_real

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-network', action='store_true')
    args = parser.parse_args()
    source = ROOT / 'data/kronos_baseline_v1/forecasts/base/20260501T152900Z.json'
    row = json.loads(source.read_text())
    paths = np.asarray(row['sampled_ohlc'])
    if paths.shape != (25, 5, 4) or not np.isfinite(paths).all():
        raise ValueError('Invalid archived paths')
    package = build_package(forecast_id='base-20260501T152900Z', origin=row['origin'],
        session=row['date'], origin_close=row['origin_close'], sampled_paths=paths.tolist(),
        kronos_median=np.median(paths[:, :, 3], axis=0).tolist(),
        kronos_range=np.quantile(paths[:, :, 3], [.1, .9], axis=0).tolist())
    package['timestamp_convention'] = 'origin is last completed bar START; decision cutoff is one minute later'
    package['target_bar_starts'] = row['targets']
    package['input_sha256'] = row['input_sha256']
    result = request_real(package, api_key=dotenv_values(ROOT / '.env').get('TYPESAFE_API_KEY'),
        allow_network=args.allow_network, cache_dir=ROOT / 'data/jev_pilot_v1')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
