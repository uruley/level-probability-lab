from __future__ import annotations

import pandas as pd
import pytest

from level_probability_lab.exceptions import ValidationError
from level_probability_lab.normalize import normalize_ohlcv
from level_probability_lab.validation import validate_normalized
from tests.conftest import make_session_frame


def test_duplicate_bars_fail_validation():
    frame = make_session_frame(n=5)
    dup = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    report = validate_normalized(dup)
    assert not report.ok
    assert any("duplicate" in e for e in report.errors)
    with pytest.raises(ValidationError):
        report.raise_if_errors()


def test_bad_ohlc_fails():
    frame = make_session_frame(n=5)
    frame.loc[0, "low"] = 999.0
    report = validate_normalized(frame)
    assert not report.ok
    assert any("OHLC" in e for e in report.errors)


def test_negative_volume_fails():
    frame = make_session_frame(n=5)
    frame.loc[1, "volume"] = -1
    report = validate_normalized(frame)
    assert not report.ok


def test_normalize_does_not_invent_prices_for_gaps():
    raw = pd.DataFrame(
        {
            "symbol": ["QQQ", "QQQ"],
            "ts_event": [
                pd.Timestamp("2024-07-01 13:30:00", tz="UTC"),
                pd.Timestamp("2024-07-01 13:32:00", tz="UTC"),
            ],
            "open": [100.0, 100.2],
            "high": [100.1, 100.3],
            "low": [99.9, 100.1],
            "close": [100.05, 100.25],
            "volume": [10, 11],
        }
    )
    normalized = normalize_ohlcv(
        raw,
        calendar_name="NYSE",
        interval_minutes=1,
        publication_lag_seconds=0,
        max_no_trade_gap_minutes=5,
        discontinuity_log_return=0.08,
        source_dataset="SYNTHETIC",
        source_schema="ohlcv-1m",
        is_synthetic=True,
    )
    gapish = normalized[normalized["bar_start"] == pd.Timestamp("2024-07-01 13:31:00", tz="UTC")]
    assert len(gapish) == 1
    assert gapish.iloc[0]["bar_status"] in {"no_trade", "coverage_gap"}
    assert pd.isna(gapish.iloc[0]["close"])
