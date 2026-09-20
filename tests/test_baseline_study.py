import numpy as np
import pandas as pd
import pytest

from level_probability_lab.baseline_study import eligible_origins, score_paths, paired_bootstrap, write_json


def test_elapsed_grid_gap_and_session_close():
    opening = pd.Timestamp("2026-06-01T13:30Z")
    closing = opening+pd.Timedelta(minutes=390)
    bars = pd.DataFrame({"bar_start":pd.date_range(opening, periods=390, freq="min")})
    origins = eligible_origins(bars, opening, closing)
    assert len(origins)==54
    assert origins[0]==opening+pd.Timedelta(minutes=119)
    assert origins[-1]+pd.Timedelta(minutes=5)==closing-pd.Timedelta(minutes=1)
    # A missing first target invalidates that forecast, not a next-five-rows shift.
    missing = bars.drop(index=120)
    assert origins[0] not in eligible_origins(missing, opening, closing)
    assert origins[-1] in eligible_origins(missing, opening, closing)


def test_neutral_direction_and_known_scores():
    scores = score_paths(np.array([[100.,102.],[100.,104.]]), [101.,102.], 100.)
    np.testing.assert_array_equal(scores["direction_valid"], [0,1])
    np.testing.assert_allclose(scores["abs_error"], [1,1])
    np.testing.assert_allclose(scores["brier"], [1,0])
    np.testing.assert_allclose(scores["baseline_abs_error"], [1,2])


def test_forecast_cannot_be_rewritten(tmp_path):
    path = tmp_path/"forecast.json"
    write_json(path, {"value":1}, True)
    with pytest.raises(FileExistsError):
        write_json(path, {"value":2}, True)


def test_bootstrap_preserves_pairing_and_session_blocks():
    frame = pd.DataFrame(dict(date=["a","a","b"], abs_error=[1.,2.,3.], baseline_abs_error=[2.,3.,4.]))
    result = paired_bootstrap(frame)
    assert result["mae_difference"]==-1
    assert result["ci95"]==[-1,-1]
    assert result["sessions"]==2
