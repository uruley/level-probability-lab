"""Inspect actual tokenizer calls during matched May development forecasts."""
import hashlib
import json
from pathlib import Path

import numpy as np

from level_probability_lab.lab import Lab, ROOT
from level_probability_lab.trade_amount import attach_amount
from level_probability_lab.ghost_candles.windows import completed_input_window, future_session_timestamps


def main():
    output = ROOT / 'data/trade_amount_v1/token_comparison'
    output.mkdir(parents=True, exist_ok=True)
    lab = Lab(output=output / 'lab')
    session = lab.sessions[lab.create('2026-05-01', 120)['session_id']]
    model = lab.get_model('base')
    original = model.tokenizer.encode
    captures = []

    def inspect(x, *args, **kwargs):
        tokens = original(x, *args, **kwargs)
        captures.append({'normalized': x.detach().cpu().numpy().copy(),
                         'tokens': [t.detach().cpu().numpy().copy() for t in tokens]})
        return tokens

    model.tokenizer.encode = inspect
    rows, arrays = [], {}
    try:
        for cursor in range(119, 340, 20):
            visible = session.bars.iloc[:cursor + 1]
            origin = visible.iloc[-1].bar_start
            window = completed_input_window(visible, origin, 120)
            actual = attach_amount(window, ROOT / 'data/trade_amount_v1/amounts.parquet')
            targets = future_session_timestamps(visible, origin, 5)
            captures.clear()
            a, _ = model.forecast_paths(window, targets, 25, 42)
            b, _ = model.forecast_paths(actual, targets, 25, 42)
            assert len(captures) == 2
            left, right = captures
            # Inference replicates the same encoded input across the 25 paths.
            for capture in captures:
                for tokens in capture['tokens']:
                    assert np.all(tokens == tokens[0])
                assert np.all(capture['normalized'] == capture['normalized'][0])
            assert np.array_equal(left['normalized'][..., :5], right['normalized'][..., :5])
            changed = [np.flatnonzero(x[0] != y[0]).tolist()
                       for x, y in zip(left['tokens'], right['tokens'])]
            approx = window.volume.to_numpy(float) * window.close.to_numpy(float)
            deltas = actual.amount.to_numpy(float) - approx
            index = len(rows)
            for name, capture in [('approximate', left), ('trades', right)]:
                arrays[f'{index}_{name}_normalized'] = capture['normalized'][0]
                for component, tokens in enumerate(capture['tokens']):
                    arrays[f'{index}_{name}_tokens_{component}'] = tokens[0]
            arrays[f'{index}_approximate_paths'] = a
            arrays[f'{index}_trades_paths'] = b
            rows.append({'origin': origin.isoformat(), 'input_start': window.iloc[0].bar_start.isoformat(),
                         'dollar_amount_max_absolute_difference': float(np.max(np.abs(deltas))),
                         'normalized_amount_max_absolute_difference': float(np.max(np.abs(left['normalized'][..., 5] - right['normalized'][..., 5]))),
                         'changed_token_positions': changed,
                         'identical_tokens': not any(changed),
                         'identical_sampled_ohlc_paths': bool(np.array_equal(a, b)),
                         'identical_median_closes': bool(np.array_equal(np.median(a[:, :, 3], axis=0), np.median(b[:, :, 3], axis=0))),
                         'max_median_close_difference': float(np.max(np.abs(np.median(a[:, :, 3], axis=0) - np.median(b[:, :, 3], axis=0))))})
    finally:
        model.tokenizer.encode = original
    np.savez_compressed(output / 'captured_tokens_and_paths.npz', **arrays)
    report = {'purpose': 'Development diagnostic, not predictive evaluation', 'session': '2026-05-01',
              'model': model.model_name, 'model_revision': model.model_revision,
              'tokenizer_revision': model.tokenizer_revision, 'lookback': 120, 'paths': 25, 'seed': 42,
              'temperature': model.temperature, 'top_p': model.top_p, 'clip': model.clip,
              'matched_origins': len(rows), 'identical_token_pairs': sum(r['identical_tokens'] for r in rows),
              'identical_path_pairs': sum(r['identical_sampled_ohlc_paths'] for r in rows),
              'identical_median_pairs': sum(r['identical_median_closes'] for r in rows), 'rows': rows}
    for name, path in [('amounts', ROOT / 'data/trade_amount_v1/amounts.parquet'), ('adapter', ROOT / 'src/level_probability_lab/ghost_candles/adapter.py')]:
        with path.open('rb') as stream:
            report[name + '_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
