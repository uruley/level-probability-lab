from __future__ import annotations

import pandas as pd
import pytest

from level_probability_lab.context import join_context
from tests.conftest import make_session_frame


def test_context_join_is_asof_backward_only():
    qqq = make_session_frame(n=10, symbol="QQQ")
    spy = make_session_frame(n=10, symbol="SPY", closes=[200.0 + i for i in range(10)])
    labels = pd.DataFrame(
        {
            "prediction_time": [qqq.iloc[5]["usable_at"]],
            "prediction_bar_start": [qqq.iloc[5]["bar_start"]],
        }
    )
    merged = join_context(labels, pd.concat([qqq, spy], ignore_index=True), "SPY", stale_seconds=60)
    assert merged.iloc[0]["context_usable_at"] <= merged.iloc[0]["prediction_time"]
    assert merged.iloc[0]["context_bar_start"] == spy.iloc[5]["bar_start"]


def test_stale_context_is_flagged_not_interpolated():
    qqq = make_session_frame(n=10, symbol="QQQ")
    spy = make_session_frame(n=3, symbol="SPY")
    labels = pd.DataFrame(
        {
            "prediction_time": [qqq.iloc[9]["usable_at"]],
            "prediction_bar_start": [qqq.iloc[9]["bar_start"]],
        }
    )
    merged = join_context(labels, pd.concat([qqq, spy], ignore_index=True), "SPY", stale_seconds=60)
    assert bool(merged.iloc[0]["context_stale"]) is True


def test_future_context_would_raise():
    qqq = make_session_frame(n=5, symbol="QQQ")
    spy = make_session_frame(n=5, symbol="SPY")
    spy.loc[:, "usable_at"] = spy["usable_at"] + pd.Timedelta(minutes=30)
    labels = pd.DataFrame(
        {
            "prediction_time": [qqq.iloc[0]["usable_at"]],
            "prediction_bar_start": [qqq.iloc[0]["bar_start"]],
        }
    )
    # asof backward should find nothing rather than a future bar
    merged = join_context(labels, pd.concat([qqq, spy], ignore_index=True), "SPY", stale_seconds=60)
    assert pd.isna(merged.iloc[0]["context_usable_at"]) or merged.iloc[0]["context_usable_at"] <= merged.iloc[0]["prediction_time"]
