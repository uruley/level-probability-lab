from __future__ import annotations

import pandas as pd

from level_probability_lab.time_model import bar_end, expected_horizon_starts, usable_at


def test_bar_end_and_usable_at_are_after_start():
    start = pd.Timestamp("2024-07-01 14:30:00", tz="UTC")
    assert bar_end(start) == pd.Timestamp("2024-07-01 14:31:00", tz="UTC")
    assert usable_at(start, publication_lag_seconds=0) == bar_end(start)
    assert usable_at(start, publication_lag_seconds=2) == pd.Timestamp("2024-07-01 14:31:02", tz="UTC")


def test_horizon_is_elapsed_minutes_not_row_count():
    completed_end = pd.Timestamp("2024-07-01 15:00:00", tz="UTC")
    starts = expected_horizon_starts(completed_end, horizon_minutes=15)
    assert len(starts) == 15
    assert starts[0] == completed_end
    assert starts[-1] == completed_end + pd.Timedelta(minutes=14)
