from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from level_probability_lab.config import Config


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def tmp_lab_root(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    return tmp_path


def make_cfg(overrides: dict | None = None, root: Path | None = None) -> Config:
    raw = {
        "prediction": {
            "symbol": "QQQ",
            "context_symbols": ["SPY"],
            "lookback_minutes": 5,
            "horizon_minutes": 15,
            "min_observed_for_vol": 4,
        },
        "boundaries": {"k_up": 1.0, "k_down": 1.0, "vol_method": "std_log_return"},
        "time": {
            "calendar": "NYSE",
            "bar_interval_minutes": 1,
            "publication_lag_seconds": 0,
            "max_no_trade_gap_minutes": 5,
            "context_stale_seconds": 60,
            "discontinuity_log_return": 0.08,
        },
        "databento": {
            "dataset": "EQUS.MINI",
            "schema": "ohlcv-1m",
            "symbols": ["QQQ", "SPY"],
            "stype_in": "raw_symbol",
            "start": "2026-08-01",
            "end": "2026-09-01",
            "download_enabled": False,
            "spending_cap_usd": 0.0,
        },
    }
    if overrides:
        _deep_update(raw, overrides)
    return Config(raw=raw, path=None, project_root=root or ROOT)


def _deep_update(base: dict, extra: dict) -> None:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def make_session_frame(
    *,
    n: int = 40,
    start: str = "2024-07-01 14:30:00",
    symbol: str = "QQQ",
    closes: list[float] | None = None,
    session_close: str | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    statuses: list[str] | None = None,
) -> pd.DataFrame:
    """Build already-normalized regular-session bars. `start` is UTC bar_start of minute 0."""
    bar_start = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=n, freq="1min")
    if closes is None:
        closes = [100.0 + 0.01 * i for i in range(n)]
    closes_f = [float(c) for c in closes]
    if highs is None:
        highs = [c + 0.02 for c in closes_f]
    if lows is None:
        lows = [c - 0.02 for c in closes_f]
    opens = [closes_f[0]] + closes_f[:-1]
    session_open = bar_start[0]
    if session_close is None:
        close_ts = bar_start[-1] + pd.Timedelta(minutes=1)
    else:
        close_ts = pd.Timestamp(session_close, tz="UTC")
    statuses = statuses or ["observed"] * n
    frame = pd.DataFrame(
        {
            "symbol": symbol,
            "bar_start": bar_start,
            "bar_end": bar_start + pd.Timedelta(minutes=1),
            "usable_at": bar_start + pd.Timedelta(minutes=1),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes_f,
            "volume": [1000] * n,
            "publisher_id": pd.NA,
            "instrument_id": pd.NA,
            "bar_status": statuses,
            "source_dataset": "SYNTHETIC",
            "source_schema": "ohlcv-1m",
            "is_synthetic": True,
            "is_regular_session": True,
            "is_early_close": False,
            "session_date": pd.Timestamp("2024-07-01"),
            "session_open": session_open,
            "session_close": close_ts,
            "discontinuity_candidate": False,
        }
    )
    return frame
