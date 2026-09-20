"""Frozen offline August expansion; run prepare, forecast, then analyze."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, BASE_REVISION, load_day
from level_probability_lab.baseline_study import eligible_origins, forecast_file, write_json
from level_probability_lab.calendar import session_schedule

OUT = ROOT / 'data/location_evaluation_v3_august'
SOURCE = ROOT / 'data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet'
PROTOCOL = ROOT / 'docs/LOCATION_EVALUATION_V3_PROTOCOL.md'


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def prepare():
    old = json.loads((ROOT/'data/kronos_baseline_v1/frozen_config.json').read_text())
    assert digest(SOURCE) == old['source_sha256']
    code = [Path(__file__).resolve(), ROOT/'scripts/analyze_location_v3.py']
    code += [ROOT/'src/level_probability_lab'/p for p in [
        'ghost_candles/adapter.py', 'lab.py', 'baseline_study.py', 'calendar.py',
        'market_context.py', 'touch_experiment.py', 'location_bands.py', 'location_evaluation.py']]
    upstream = {str(p.relative_to(Path(r'C:\Users\ruley\Kronos'))): digest(p)
                for p in sorted(Path(r'C:\Users\ruley\Kronos\model').rglob('*.py'))}
    assert upstream == old['kronos_python_sha256']
    origins = []
    coverage = []
    for date in session_schedule('2026-08-01', '2026-08-31').index:
        day = str(date.date()); bars = load_day(SOURCE, day)
        eligible = eligible_origins(bars, bars.iloc[0].session_open, bars.iloc[0].session_close)
        assert len(bars) == 390 and len(eligible) == 54
        coverage.append(dict(date=day, bars=len(bars), origins=len(eligible)))
        origins.extend(dict(date=day, origin=t.isoformat()) for t in eligible)
    assert len(origins) == 1134 and len(coverage) == 21
    config = dict(source_sha256=old['source_sha256'], protocol_sha256=digest(PROTOCOL),
        base_revision=BASE_REVISION, tokenizer_revision=old['tokenizer_revision'],
        lookback=120, horizon=5, sample_count=25, seed=42, stride_minutes=5,
        temperature=1., top_p=.9, top_k=0, max_context=512, clip=5,
        amount='volume * close', exposure='previously inspected August development',
        july='past indicator warmup only; no July forecast/outcome evaluation',
        code={str(p.relative_to(ROOT)):digest(p) for p in code},
        upstream_code=upstream, origins=origins, coverage=coverage,
        reference_manifest_sha256=digest(ROOT/'data/location_evaluation_v2/manifest.json'))
    if (OUT/'frozen_config.json').exists():
        assert json.loads((OUT/'frozen_config.json').read_text()) == config, 'Frozen run changed'
    else:
        OUT.mkdir(exist_ok=False)
        write_json(OUT/'frozen_config.json', config, True)
        (OUT/'protocol.md').write_bytes(PROTOCOL.read_bytes())
    return config


def forecast(config):
    from level_probability_lab.ghost_candles.adapter import KronosPathForecaster
    forecaster = None; last_day = None; started = time.monotonic()
    for count, item in enumerate(config['origins'], 1):
        if item['date'] != last_day:
            bars = load_day(SOURCE, item['date']).set_index('bar_start', drop=False)
            last_day = item['date']
        t = pd.Timestamp(item['origin'])
        window = bars.loc[t-pd.Timedelta(minutes=119):t].reset_index(drop=True)
        targets = pd.date_range(t+pd.Timedelta(minutes=1), periods=5, freq='min')
        ih = hashlib.sha256(window[['bar_start','open','high','low','close','volume']].to_csv(index=False).encode()).hexdigest()
        expected = dict(**item, model='base', origin_close=float(window.iloc[-1].close),
                        input_sha256=ih, targets=[v.isoformat() for v in targets])
        path = forecast_file(OUT, 'base', item['origin'])
        if path.exists():
            cached = json.loads(path.read_text())
            assert all(cached[k] == v for k,v in expected.items()), 'Invalid cached forecast'
            paths = np.asarray(cached['sampled_ohlc'])
        else:
            if forecaster is None:
                forecaster = KronosPathForecaster(model_id='NeoQuasar/Kronos-base',
                    model_revision=config['base_revision'], tokenizer_revision=config['tokenizer_revision'],
                    cache_dir=ROOT/'data/models/hub', max_context=512, clip=5,
                    temperature=1., top_p=.9, top_k=0)
            paths, seconds = forecaster.forecast_paths(window, targets, 25, 42)
            assert paths.shape == (25,5,4) and np.isfinite(paths).all()
            write_json(path, dict(**expected, sampled_ohlc=paths.tolist(), inference_seconds=seconds), True)
        assert paths.shape == (25,5,4) and np.isfinite(paths).all()
        if count % 25 == 0 or count == len(config['origins']):
            progress = dict(status='forecasting' if count < len(config['origins']) else 'forecasts_complete',
                completed=count, total=len(config['origins']), elapsed_seconds=round(time.monotonic()-started,1))
            write_json(OUT/'progress.json', progress)
            print(json.dumps(progress), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare','forecast','analyze'])
    args=parser.parse_args()
    config=prepare()
    if args.phase == 'forecast':
        lock=OUT/'forecast.lock'
        with lock.open('x') as f: f.write('Active frozen inference run')
        try: forecast(config)
        finally: lock.unlink()
    elif args.phase == 'analyze':
        from analyze_location_v3 import analyze
        analyze(OUT, SOURCE, config)
    else: print('Frozen: 1134 origins across 21 August development sessions', flush=True)
