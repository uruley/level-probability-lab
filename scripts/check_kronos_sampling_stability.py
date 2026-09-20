"""Fixed May development windows; vary only the sampling seed."""
import hashlib
import json
import numpy as np
from level_probability_lab.lab import Lab, ROOT
from level_probability_lab.ghost_candles.windows import completed_input_window, future_session_timestamps


def main():
    output = ROOT / 'data/trade_amount_v1/sampling_stability'
    output.mkdir(parents=True, exist_ok=True)
    lab = Lab(output=output / 'lab')
    session = lab.sessions[lab.create('2026-05-01', 120)['session_id']]
    model = lab.get_model('base')
    seeds = [42, 43, 44, 45, 46]
    rows, captures, deltas, widths = [], {}, [], []
    replay_identical = None
    for index, cursor in enumerate(range(119, 340, 20)):
        visible = session.bars.iloc[:cursor+1]
        origin = visible.iloc[-1].bar_start
        window = completed_input_window(visible, origin, 120)
        targets = future_session_timestamps(visible, origin, 5)
        paths = []
        for seed in seeds:
            sampled, _ = model.forecast_paths(window, targets, 25, seed)
            assert sampled.shape == (25, 5, 4) and np.isfinite(sampled).all()
            paths.append(sampled)
        if index == 0:
            replay, _ = model.forecast_paths(window, targets, 25, 42)
            replay_identical = bool(np.array_equal(replay, paths[0]))
        paths = np.stack(paths)
        medians = np.median(paths[:, :, :, 3], axis=1)
        spread = np.ptp(medians, axis=0)
        delta = np.abs(medians[1:] - medians[0])
        band_width = np.quantile(paths[:, :, :, 3], .9, axis=1) - np.quantile(paths[:, :, :, 3], .1, axis=1)
        deltas.append(delta)
        widths.append(band_width)
        captures[f'{index}_paths'] = paths
        captures[f'{index}_input_ohlcv'] = window[['open','high','low','close','volume']].to_numpy()
        rows.append({'origin': origin.isoformat(), 'target_timestamps': [t.isoformat() for t in targets],
                     'median_closes_by_seed': medians.tolist(), 'median_close_range_across_seeds': spread.tolist(),
                     'input_sha256': hashlib.sha256(window.to_json(date_format='iso', double_precision=15).encode()).hexdigest()})
    delta = np.stack(deltas)
    report = {'purpose': 'Sampling sensitivity only, no predictive accuracy or holdout evaluation',
              'session': '2026-05-01', 'model': model.model_name, 'model_revision': model.model_revision,
              'tokenizer_revision': model.tokenizer_revision, 'amount_mode': 'approximate',
              'lookback': 120, 'paths_per_forecast': 25, 'seeds': seeds, 'origins': len(rows),
              'temperature': model.temperature, 'top_p': model.top_p, 'top_k': model.top_k,
              'same_seed_repeat_identical': replay_identical,
              'mean_absolute_median_change_vs_seed42_by_horizon': delta.mean(axis=(0,1)).tolist(),
              'max_absolute_median_change_vs_seed42': float(delta.max()),
              'median_range_across_seeds_by_horizon': np.median([r['median_close_range_across_seeds'] for r in rows], axis=0).tolist(),
              'mean_sample_band_width_by_horizon': np.stack(widths).mean(axis=(0,1)).tolist(),
              'rows': rows}
    np.savez_compressed(output / 'paths_and_inputs.npz', **captures)
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}, indent=2))


if __name__ == '__main__':
    main()
