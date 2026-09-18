from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from level_probability_lab.exceptions import EnvironmentMismatch, ForecastLocked, SessionBoundaryError
from level_probability_lab.ghost_candles.env import validate_env
from level_probability_lab.ghost_candles.ohlc import (
    is_valid_ohlc,
    representative_path,
    repair_ohlc,
    uncertainty_region,
)
from level_probability_lab.ghost_candles.replay import run_replay
from level_probability_lab.ghost_candles.scoring import persistence_recent_range_baseline, score_forecasts
from level_probability_lab.ghost_candles.storage import ForecastStore
from level_probability_lab.ghost_candles.windows import completed_input_window, future_session_timestamps
from tests.conftest import make_session_frame


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def _ok_env(**overrides) -> dict:
    env = {
        "executable": r"C:\Users\ruley\AiStcockProbabilitydoctor\.venv\Scripts\python.exe",
        "torch_version": "2.12.0.dev20260408+cu128",
        "torch_cuda": "12.8",
        "cuda_available": True,
        "device_name": "NVIDIA GeForce RTX 5070",
    }
    env.update(overrides)
    return env


def test_intended_cuda_environment_is_accepted():
    validate_env(_ok_env())


def test_hermes_agent_cu121_venv_is_rejected():
    with pytest.raises(EnvironmentMismatch, match="project venv"):
        validate_env(
            _ok_env(
                executable=r"C:\Users\ruley\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe",
                torch_version="2.5.1+cu121",
            )
        )


def test_cpu_fallback_is_rejected():
    with pytest.raises(EnvironmentMismatch, match="CUDA"):
        validate_env(_ok_env(cuda_available=False, device_name=""))


def test_wrong_gpu_is_rejected():
    with pytest.raises(EnvironmentMismatch, match="5070"):
        validate_env(_ok_env(device_name="NVIDIA GeForce RTX 4090"))


def test_live_process_is_project_cuda_venv():
    from level_probability_lab.ghost_candles.env import collect_env

    validate_env(collect_env())


# ---------------------------------------------------------------------------
# No future leakage / timestamps
# ---------------------------------------------------------------------------


def test_input_window_cannot_include_future_bars():
    bars = make_session_frame(n=20)
    last = bars.iloc[9]["bar_start"]
    window = completed_input_window(bars, last_bar_start=last, lookback=5)
    assert len(window) == 5
    assert window["bar_start"].max() == last
    assert (window["bar_start"] <= last).all()
    future_close = float(bars.loc[bars["bar_start"] > last, "close"].sum())
    assert future_close != 0.0
    assert float(window["close"].sum()) != future_close


def test_mutating_future_ohlc_does_not_change_input_window():
    bars = make_session_frame(n=20)
    last = bars.iloc[9]["bar_start"]
    before = completed_input_window(bars, last_bar_start=last, lookback=5).copy()
    mutated = bars.copy()
    mutated.loc[mutated["bar_start"] > last, ["open", "high", "low", "close"]] = 999.0
    after = completed_input_window(mutated, last_bar_start=last, lookback=5)
    pd.testing.assert_frame_equal(
        before[["bar_start", "open", "high", "low", "close"]].reset_index(drop=True),
        after[["bar_start", "open", "high", "low", "close"]].reset_index(drop=True),
    )


def test_exactly_five_chronological_future_timestamps():
    bars = make_session_frame(n=20)
    last = bars.iloc[9]["bar_start"]
    ts = future_session_timestamps(bars, last_bar_start=last, horizon=5)
    assert len(ts) == 5
    assert list(ts) == list(pd.date_range(last + pd.Timedelta(minutes=1), periods=5, freq="1min"))
    assert (ts > last).all()
    assert ts.is_monotonic_increasing
    assert ts.is_unique


def test_session_boundary_blocks_forecast_past_close():
    bars = make_session_frame(n=12, session_close="2024-07-01 14:42:00")
    last = bars.iloc[9]["bar_start"]
    with pytest.raises(SessionBoundaryError):
        future_session_timestamps(bars, last_bar_start=last, horizon=5)


def test_gap_in_lookback_is_rejected():
    bars = make_session_frame(n=20).drop(index=7).reset_index(drop=True)
    last = bars.iloc[10]["bar_start"]
    with pytest.raises(SessionBoundaryError, match="contiguous"):
        completed_input_window(bars, last_bar_start=last, lookback=8)


# ---------------------------------------------------------------------------
# OHLC validity / representative path
# ---------------------------------------------------------------------------


def test_invalid_ohlc_is_detected():
    assert is_valid_ohlc(10.0, 11.0, 9.0, 10.5)
    assert not is_valid_ohlc(10.0, 9.5, 9.0, 10.2)  # high < open
    assert not is_valid_ohlc(10.0, 11.0, 10.5, 10.2)  # low > close
    assert not is_valid_ohlc(10.0, 9.0, 11.0, 10.0)  # high < low


def test_representative_path_is_a_real_sample_not_ohlc_average():
    paths = np.array(
        [
            [[10.0, 11.0, 9.5, 10.5], [10.5, 12.0, 10.0, 11.5], [11.5, 12.0, 11.0, 11.2], [11.2, 11.4, 10.8, 11.0], [11.0, 11.1, 10.7, 10.8]],
            [[10.0, 10.4, 9.8, 10.1], [10.1, 10.3, 9.9, 10.0], [10.0, 10.2, 9.8, 9.9], [9.9, 10.0, 9.7, 9.8], [9.8, 9.9, 9.6, 9.7]],
            [[10.0, 10.6, 9.9, 10.3], [10.3, 10.8, 10.1, 10.4], [10.4, 10.7, 10.2, 10.5], [10.5, 10.8, 10.3, 10.6], [10.6, 10.9, 10.4, 10.7]],
        ],
        dtype=np.float64,
    )
    chosen = representative_path(paths)
    matches = [np.allclose(chosen, p) for p in paths]
    assert sum(matches) == 1
    avg = paths.mean(axis=0)
    assert not np.allclose(chosen, avg)


def test_repair_ohlc_restores_invariants():
    o, h, l, c = repair_ohlc(10.0, 9.0, 11.0, 10.5)
    assert is_valid_ohlc(o, h, l, c)


def test_uncertainty_region_uses_sample_percentiles():
    rng = np.random.default_rng(0)
    paths = np.zeros((20, 5, 4))
    paths[:, :, 0] = 10
    paths[:, :, 3] = 10
    paths[:, :, 1] = 11 + rng.normal(0, 0.2, size=(20, 5))
    paths[:, :, 2] = 9 + rng.normal(0, 0.2, size=(20, 5))
    low, high = uncertainty_region(paths, low_q=0.1, high_q=0.9)
    assert low.shape == (5,)
    assert high.shape == (5,)
    assert np.all(low <= high)


# ---------------------------------------------------------------------------
# Storage immutability
# ---------------------------------------------------------------------------


def _fake_forecast(fid: str = "f1") -> dict:
    return {
        "forecast_id": fid,
        "symbol": "QQQ",
        "sampled_paths": [[[1, 2, 0, 1]] * 5] * 2,
        "displayed_path": [[1, 2, 0, 1]] * 5,
    }


def test_forecast_cannot_be_overwritten(tmp_path: Path):
    store = ForecastStore(tmp_path / "forecasts.jsonl")
    store.put(_fake_forecast("abc"))
    with pytest.raises(ForecastLocked):
        store.put(_fake_forecast("abc"))
    loaded = store.all()
    assert len(loaded) == 1


# ---------------------------------------------------------------------------
# Replay + scoring + seed
# ---------------------------------------------------------------------------


class _SeededForecaster:
    model_name = "fake-kronos"
    model_revision = "test"
    tokenizer_name = "fake-tok"
    tokenizer_revision = "test"

    def forecast_paths(self, window, future_ts, sample_count: int, seed: int):
        rng = np.random.default_rng(seed + int(window["close"].sum() * 1000))
        last = float(window.iloc[-1]["close"])
        paths = np.zeros((sample_count, len(future_ts), 4), dtype=np.float64)
        for s in range(sample_count):
            price = last
            for t in range(len(future_ts)):
                delta = rng.normal(0, 0.05)
                o = price
                c = price + delta
                h = max(o, c) + abs(rng.normal(0, 0.02))
                l = min(o, c) - abs(rng.normal(0, 0.02))
                paths[s, t] = [o, h, l, c]
                price = c
        return paths, 0.012


def test_replay_never_feeds_future_bars_to_forecaster():
    bars = make_session_frame(n=20)
    seen_max: list[pd.Timestamp] = []

    class Spy(_SeededForecaster):
        def forecast_paths(self, window, future_ts, sample_count, seed):
            seen_max.append(window["bar_start"].max())
            assert window["bar_start"].max() < future_ts.min()
            return super().forecast_paths(window, future_ts, sample_count, seed)

    store = ForecastStore.__new__(ForecastStore)
    store.path = None
    store._rows = []
    store._ids = set()

    def put(row):
        if row["forecast_id"] in store._ids:
            raise ForecastLocked(row["forecast_id"])
        store._ids.add(row["forecast_id"])
        store._rows.append(row)

    store.put = put  # type: ignore[method-assign]
    store.all = lambda: list(store._rows)  # type: ignore[method-assign]

    run_replay(
        bars,
        forecaster=Spy(),
        store=store,
        lookback=5,
        horizon=5,
        sample_count=3,
        seed=7,
        env_metadata=_ok_env(),
    )
    assert seen_max
    assert max(seen_max) <= bars.iloc[-6]["bar_start"]


def test_fixed_seed_replay_is_identical(tmp_path: Path):
    bars = make_session_frame(n=18)
    a = ForecastStore(tmp_path / "a.jsonl")
    b = ForecastStore(tmp_path / "b.jsonl")
    c = ForecastStore(tmp_path / "c.jsonl")
    kwargs = dict(lookback=5, horizon=5, sample_count=4, env_metadata=_ok_env())
    run_replay(bars, _SeededForecaster(), a, seed=11, **kwargs)
    run_replay(bars, _SeededForecaster(), b, seed=11, **kwargs)
    run_replay(bars, _SeededForecaster(), c, seed=99, **kwargs)
    pa = [row["sampled_paths"] for row in a.all()]
    pb = [row["sampled_paths"] for row in b.all()]
    pc = [row["sampled_paths"] for row in c.all()]
    assert pa == pb
    assert pa != pc
    assert len(pa) > 0
    for row in a.all():
        assert len(row["target_timestamps"]) == 5
        assert len(row["displayed_path"]) == 5
        assert len(row["sampled_paths"]) == 4


def test_scoring_compares_kronos_to_baseline_on_same_timestamps():
    bars = make_session_frame(n=16)
    last = bars.iloc[7]
    targets = list(bars.iloc[8:13]["bar_start"])
    displayed = []
    for i in range(5):
        actual = bars.iloc[8 + i]
        displayed.append(
            [float(actual["open"]) + 0.5, float(actual["high"]) + 0.5, float(actual["low"]) + 0.5, float(actual["close"]) + 0.5]
        )
    forecast = {
        "forecast_id": "s1",
        "symbol": "QQQ",
        "last_input_timestamp": last["bar_start"].isoformat(),
        "target_timestamps": [t.isoformat() for t in targets],
        "displayed_path": displayed,
        "sampled_paths": [displayed] * 2,
        "inference_time_s": 0.04,
        "input_window": [{"bar_start": last["bar_start"].isoformat(), "close": float(last["close"])}],
    }
    scored = score_forecasts([forecast], bars)
    assert set(scored["horizon_minutes"].unique()) == {1, 2, 3, 4, 5}
    assert (scored["kronos_close_abs_error"] > 0).all()
    assert "baseline_close_abs_error" in scored.columns
    assert "kronos_direction_hit" in scored.columns
    assert "inference_time_s" in scored.columns
