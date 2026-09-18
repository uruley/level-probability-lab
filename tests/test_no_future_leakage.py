from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.context import join_context
from level_probability_lab.labeling import build_labels
from tests.conftest import make_cfg, make_session_frame


def test_lookback_and_context_never_use_future_bars():
    n = 40
    closes = [100.0 + 0.04 * np.sin(i / 3) for i in range(n)]
    qqq = make_session_frame(n=n, symbol="QQQ", closes=closes, session_close="2024-07-01 16:00:00")
    spy_closes = [200.0 + 0.03 * np.sin(i / 3) for i in range(n)]
    spy = make_session_frame(n=n, symbol="SPY", closes=spy_closes, session_close="2024-07-01 16:00:00")
    cfg = make_cfg()
    labels = build_labels(qqq, cfg.get)
    labels = join_context(labels, pd.concat([qqq, spy], ignore_index=True), "SPY", stale_seconds=60)
    usable = labels[labels["lookback_last_start"].notna()]
    assert not usable.empty
    assert (usable["lookback_last_start"] <= usable["prediction_bar_start"]).all()
    assert (usable["lookback_first_start"] <= usable["prediction_bar_start"]).all()
    has_ctx = labels[labels["context_usable_at"].notna()]
    assert not has_ctx.empty
    assert (has_ctx["context_usable_at"] <= has_ctx["prediction_time"]).all()
