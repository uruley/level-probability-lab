import numpy as np
import pytest
from level_probability_lab.jev_compact import build_compact

def fixture():
    return dict(origin='2026-05-01T15:29:00+00:00', model='base', origin_close=100,
        sampled_ohlc=np.tile([100, 101, 99, 100], (3, 5, 1)).tolist(),
        targets=[f'2026-05-01T15:{m}:00+00:00' for m in range(30,35)])

def test_summary_ignores_outcomes_and_is_deterministic():
    row = fixture()
    package, digest = build_compact(row)
    assert build_compact(dict(row, actual_close=999, future_news='secret')) == (package, digest)
    assert package['cutoff'] == '2026-05-01T15:30:00+00:00'
    assert package['target_final_close'] == '2026-05-01T15:35:00+00:00'
    assert package['kronos']['final_class_frequencies']['neutral'] == 1

def test_invalid_high_low_is_reported_not_repaired():
    row = fixture(); row['sampled_ohlc'][0][0][1] = 98
    package, _ = build_compact(row)
    assert package['kronos']['invalid_ohlc_path_count'] == 1
    assert row['sampled_ohlc'][0][0][1] == 98

def test_rejects_gaps_july_and_nonfinite():
    row = fixture()
    row['targets'][0] = row['targets'][1]
    with pytest.raises(ValueError): build_compact(row)
    row = fixture(); row['origin'] = '2026-07-01T15:29Z'
    with pytest.raises(ValueError): build_compact(row)
    row = fixture(); row['sampled_ohlc'][0][0][0] = float('nan')
    with pytest.raises(ValueError): build_compact(row)
