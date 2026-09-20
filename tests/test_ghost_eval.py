from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from level_probability_lab.ghost_candles.analogues import AnalogueIndex, analogue_overlap_report
from level_probability_lab.ghost_candles.direction import directional_hit, move_sign, summarize_direction
from level_probability_lab.ghost_candles.distribution import sample_horizon_stats
from level_probability_lab.ghost_candles.evaluate import score_engine
from tests.conftest import make_session_frame


def test_persistence_zero_change_is_neutral_not_a_direction_call():
    origin = 100.0
    assert move_sign(100.0, origin) == 0
    assert directional_hit(forecast_close=100.0, actual_close=101.0, origin_close=origin) is None
    assert directional_hit(forecast_close=101.0, actual_close=101.0, origin_close=origin) == 1.0
    assert directional_hit(forecast_close=99.0, actual_close=101.0, origin_close=origin) == 0.0


def test_direction_summary_does_not_score_neutral_as_wrong():
    hits = [None, None, 1.0, 0.0, 1.0]
    summary = summarize_direction(hits)
    assert summary["n_directional"] == 3
    assert summary["n_neutral"] == 2
    assert summary["directional_accuracy"] == pytest.approx(2 / 3)
    assert summary["neutral_rate"] == pytest.approx(2 / 5)
    assert summary["directional_accuracy_including_neutral_as_miss"] is None or summary["scored_as_directional_model"] is False


def test_sample_stats_use_full_distribution_not_a_single_path():
    origin = 100.0
    paths = np.zeros((10, 5, 4))
    # 7 paths finish above origin, 3 below, at horizon 1
    paths[:, 0, 0] = 100.0
    paths[:, 0, 1] = 101.0
    paths[:, 0, 2] = 99.0
    paths[:7, 0, 3] = 101.0
    paths[7:, 0, 3] = 99.0
    paths[:, 1:, :] = paths[:, 0:1, :]
    stats = sample_horizon_stats(paths, origin_close=origin)
    assert len(stats) == 5
    h1 = stats[0]
    assert h1["horizon_minutes"] == 1
    assert h1["median_close"] == pytest.approx(101.0)
    assert h1["p_close_gt_origin"] == pytest.approx(0.7)
    assert h1["p_close_lt_origin"] == pytest.approx(0.3)
    assert "close_q10" in h1 and "close_q90" in h1
    assert "high_q90" in h1 and "low_q10" in h1
    assert "range_q50" in h1
    assert "max_upside_q50" in h1
    assert "max_downside_q50" in h1


def test_analogues_cannot_use_windows_at_or_after_origin():
    day1 = make_session_frame(n=30, start="2024-07-01 14:30:00", session_close="2024-07-01 15:00:00")
    day2 = make_session_frame(n=30, start="2024-07-02 14:30:00", session_close="2024-07-02 15:00:00")
    day2["session_date"] = pd.Timestamp("2024-07-02")
    day1["session_date"] = pd.Timestamp("2024-07-01")
    history = pd.concat([day1, day2], ignore_index=True)
    index = AnalogueIndex(lookback=5, horizon=5, k=3)
    index.fit(history)
    origin_row = day2.iloc[10]
    window = day2.iloc[6:11]
    paths, meta = index.query(window, origin_bar_start=origin_row["bar_start"])
    assert meta["n"] > 0
    for end in meta["analogue_horizon_last_starts"]:
        assert pd.Timestamp(end) < origin_row["bar_start"]
    for end in meta["analogue_lookback_last_starts"]:
        assert pd.Timestamp(end) < origin_row["bar_start"]
    for end in meta["analogue_future_ends"]:
        assert pd.Timestamp(end) < origin_row["bar_start"]


def test_overlapping_analogues_are_disclosed():
    starts = pd.date_range("2024-07-01 14:30:00", periods=8, freq="1min", tz="UTC")
    windows = [(starts[i], starts[i] + pd.Timedelta(minutes=4)) for i in range(4)]
    report = analogue_overlap_report(windows)
    assert report["n_pairs"] > 0
    assert report["n_overlapping_pairs"] > 0
    assert 0 < report["mean_overlap_fraction"] <= 1


def test_score_engine_marks_persistence_direction_undefined(tmp_path):
    bars = make_session_frame(n=16)
    last = bars.iloc[7]
    targets = list(bars.iloc[8:13]["bar_start"])
    origin = float(last["close"])
    forecast = {
        "forecast_id": "persist-1",
        "engine": "persistence",
        "last_input_timestamp": last["bar_start"].isoformat(),
        "target_timestamps": [t.isoformat() for t in targets],
        "displayed_path": [[origin, origin + 0.1, origin - 0.1, origin] for _ in range(5)],
        "sampled_paths": [[[origin, origin + 0.1, origin - 0.1, origin] for _ in range(5)]],
        "input_window": [
            {
                "bar_start": last["bar_start"].isoformat(),
                "open": float(last["open"]),
                "high": float(last["high"]),
                "low": float(last["low"]),
                "close": origin,
                "volume": float(last["volume"]),
            }
        ],
        "inference_time_s": 0.0,
    }
    scored = score_engine([forecast], bars, engine="persistence")
    assert scored["stance"].eq(0).all()
    assert scored["directional_hit"].isna().all()
    assert "median_close_abs_error" in scored.columns
    assert "p_close_gt_origin" in scored.columns
