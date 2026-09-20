from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from level_probability_lab.exceptions import AnalogueLeakageError
from level_probability_lab.ghost_candles.analogues import (
    AnalogueIndex,
    assert_analogues_known_before_origin,
    neighbor_weights,
)
from level_probability_lab.ghost_candles.kronos_calibration import apply_interval_scale, fit_interval_scale
from level_probability_lab.ghost_candles.prob_metrics import (
    brier_skill_score,
    log_loss,
    reliability_table,
    session_blocked_metrics,
    train_climatology,
)
from tests.conftest import make_session_frame


def test_session_bootstrap_resamples_sessions_not_minutes():
    rows = []
    for day, p in (("2024-01-02", 0.8), ("2024-01-03", 0.2)):
        for i in range(20):
            rows.append(
                {
                    "session_date": day,
                    "p_close_gt_origin": p,
                    "actual_up": 1 if i < 10 else 0,
                    "subsequent_return": 0.001 * i,
                }
            )
    frame = pd.DataFrame(rows)
    out = session_blocked_metrics(frame, p_clim=0.5, n_bootstrap=50, seed=1)
    assert out["n"] == 40
    assert out["n_sessions"] == 2
    assert "sessions" in out["independence_note"]
    assert out["brier_session_bootstrap_95"]["lo"] is not None


def test_log_loss_and_bss_finite():
    y = np.array([1.0, 0.0, 1.0, 0.0])
    p = np.array([0.7, 0.2, 0.6, 0.4])
    assert np.isfinite(log_loss(y, p))
    assert brier_skill_score(y, p, 0.5) > 0


def test_reliability_bins_keep_counts_and_returns():
    rng = np.random.default_rng(0)
    p = np.concatenate([np.full(40, 0.3), np.full(40, 0.7)])
    y = (rng.random(80) < p).astype(float)
    r = np.where(y == 1, 0.01, -0.01)
    table = reliability_table(y, p, r, min_count=10)
    assert table
    assert all("n" in row and "actual_event_rate" in row for row in table)


def test_analogue_future_end_must_precede_origin():
    origin = pd.Timestamp("2024-07-02 15:00:00", tz="UTC")
    ok = pd.Timestamp("2024-07-02 14:59:00", tz="UTC")
    bad = pd.Timestamp("2024-07-02 15:00:00", tz="UTC")
    assert_analogues_known_before_origin([ok], origin)
    with pytest.raises(AnalogueLeakageError):
        assert_analogues_known_before_origin([bad], origin)


def test_same_session_analogue_cannot_use_unfinished_horizon():
    day = make_session_frame(n=40, start="2024-07-01 14:30:00", session_close="2024-07-01 15:10:00")
    index = AnalogueIndex(lookback=5, horizon=5, k=5)
    index.fit(day)
    origin_row = day.iloc[20]
    window = day.iloc[16:21]
    _paths, meta = index.query(window, origin_bar_start=origin_row["bar_start"])
    origin = pd.Timestamp(origin_row["bar_start"])
    for end in meta["analogue_future_ends"]:
        assert pd.Timestamp(end) < origin
    assert "analogue_lookback_first_starts" in meta
    assert "analogue_horizon_first_starts" in meta
    assert meta["weighting"] == "uniform"


def test_neighbor_weighting_sums_to_one():
    d = np.array([0.1, 0.2, 0.5])
    for method in ("uniform", "inverse-distance", "gaussian"):
        w = neighbor_weights(d, method)
        assert pytest.approx(float(w.sum()), abs=1e-9) == 1.0


def test_kronos_interval_scale_widens_undercoverage():
    n = 80
    actual = 100 + 0.15 * np.linspace(-1, 1, n)
    median = np.full(n, 100.0)
    frame = pd.DataFrame(
        {
            "actual_close": actual,
            "median_close": median,
            "close_q10": median - 0.02,
            "close_q90": median + 0.02,
        }
    )
    scale = fit_interval_scale(frame, target_coverage=0.8)
    assert scale > 1.0
    calibrated = apply_interval_scale(frame, scale)
    assert calibrated["actual_in_calibrated_q10_q90"].mean() >= 0.75


def test_train_climatology_uses_only_sessions_through_cutoff():
    d1 = make_session_frame(n=20, start="2023-12-29 14:30:00", session_close="2023-12-29 14:50:00")
    d1["session_date"] = pd.Timestamp("2023-12-29")
    d2 = make_session_frame(n=20, start="2024-01-02 14:30:00", session_close="2024-01-02 14:50:00")
    d2["session_date"] = pd.Timestamp("2024-01-02")
    history = pd.concat([d1, d2], ignore_index=True)
    clim = train_climatology(history, horizon=2, last_session="2023-12-29")
    assert 1 in clim and 2 in clim
    assert 0 <= clim[1] <= 1
