from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.labeling import build_labels, classify_future_path, freeze_boundaries
from level_probability_lab.time_model import expected_horizon_starts
from tests.conftest import make_cfg, make_session_frame


def _path_dict(starts, highs, lows, statuses=None):
    statuses = statuses or ["observed"] * len(starts)
    out = {}
    for start, high, low, status in zip(starts, highs, lows, statuses, strict=True):
        ts = pd.Timestamp(start)
        out[ts] = {"bar_start": ts, "high": high, "low": low, "bar_status": status}
    return out


def test_upper_first_ordinary():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    highs = [100.1] * 15
    lows = [99.9] * 15
    highs[2] = 101.5
    future = _path_dict(expected, highs, lows)
    label, reason = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "upper_first"
    assert "upper" in reason


def test_lower_first_ordinary():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    highs = [100.1] * 15
    lows = [99.9] * 15
    lows[1] = 98.0
    future = _path_dict(expected, highs, lows)
    label, _ = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "lower_first"


def test_neither_when_no_touch():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    future = _path_dict(expected, [100.2] * 15, [99.8] * 15)
    label, reason = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "neither"
    assert reason == "no_boundary_touch"


def test_same_bar_ambiguity_is_not_a_class_label():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    highs = [100.2] * 15
    lows = [99.8] * 15
    highs[0] = 102.0
    lows[0] = 98.0
    future = _path_dict(expected, highs, lows)
    label, reason = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "ambiguous"
    assert label != "neither"
    assert "both" in reason


def test_incomplete_when_horizon_past_session_close():
    completed_end = pd.Timestamp("2024-07-01 19:50:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    future = _path_dict(expected, [100.2] * 15, [99.8] * 15)
    session_close = pd.Timestamp("2024-07-01 20:00:00", tz="UTC")
    label, reason = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=session_close,
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "incomplete"
    assert label != "neither"
    assert reason == "horizon_beyond_session"


def test_coverage_gap_in_horizon_is_incomplete_not_neither():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    statuses = ["observed"] * 15
    statuses[3] = "coverage_gap"
    future = _path_dict(expected, [100.2] * 15, [99.8] * 15, statuses)
    label, reason = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "incomplete"
    assert reason == "coverage_gap"


def test_timestamp_gaps_use_elapsed_grid_not_row_count():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    # Only 3 future rows exist, even though 15 elapsed minutes are required.
    future = _path_dict(expected[:3], [100.2] * 3, [99.8] * 3)
    label, reason = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "incomplete"
    assert reason == "missing_horizon_bar"


def test_no_trade_minutes_do_not_touch_and_are_not_gaps():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    expected = expected_horizon_starts(completed_end, 15)
    statuses = ["no_trade" if i % 2 else "observed" for i in range(15)]
    future = _path_dict(expected, [100.2] * 15, [99.8] * 15, statuses)
    label, _ = classify_future_path(
        future, expected, upper=101.0, lower=99.0,
        session_close=completed_end + pd.Timedelta(hours=2),
        horizon_end=completed_end + pd.Timedelta(minutes=15),
        interval_minutes=1,
    )
    assert label == "neither"


def test_build_labels_ordinary_upper_and_session_boundary():
    # Varying closes so vol > 0. Lookback=5, min_observed=4, horizon=15.
    n = 40
    closes = [100.0 + 0.05 * np.sin(i / 2) for i in range(n)]
    # Keep default wicks inside the 1-sigma band so only the planted bar hits.
    highs = [c + 1e-6 for c in closes]
    lows = [c - 1e-6 for c in closes]
    # Force an upper hit on a horizon bar after index 20's close.
    # Prediction at i=20 uses future starts i=21..35.
    highs[22] = closes[20] + 10.0
    session_close = "2024-07-01 15:10:00"  # 40 minutes after 14:30 is 15:10
    qqq = make_session_frame(n=n, closes=closes, highs=highs, lows=lows, session_close=session_close)
    cfg = make_cfg()
    labels = build_labels(qqq, cfg.get)
    assert not labels.empty
    valid = labels[labels["label"] == "upper_first"]
    assert len(valid) >= 1
    # Last bars cannot fit a 15-minute horizon inside 15:10 close.
    incomplete = labels[labels["label"] == "incomplete"]
    assert (incomplete["reason"] == "horizon_beyond_session").any()
    assert "neither" not in set(incomplete["label"])


def test_freeze_boundaries_use_only_supplied_vol():
    upper, lower = freeze_boundaries(100.0, 0.5, 1.0, 2.0)
    assert upper == 100.5
    assert lower == 99.0
