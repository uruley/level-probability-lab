import pandas as pd
import numpy as np
import pytest
from pathlib import Path

from level_probability_lab.trade_features import build_local, minute_features, normalize_trades, FEATURES


def tape():
    return pd.DataFrame({"ts_recv": pd.to_datetime(["2026-05-04T13:30:01Z", "2026-05-04T13:30:59Z", "2026-05-04T13:31:00Z"]),
                         "price": [100., 102., 999.], "size": [30, 70, 10], "side": ["B", "N", "A"], "flags": [0, 0, 0]})


def test_receive_cutoff_and_no_future_contamination():
    original = minute_features(tape())
    changed = tape()
    changed.loc[2, ["price", "size"]] = [1., 99999]
    pd.testing.assert_series_equal(original.iloc[0], minute_features(changed).iloc[0])
    first = original.iloc[0]
    assert first.available_at == pd.Timestamp("2026-05-04T13:31:00Z")
    assert first.last_received_at < first.available_at
    assert first.close == 102
    assert first.known_signed_fraction == .3
    assert first.unknown_fraction == .7
    assert first.within_minute_realized_var == pytest.approx(np.log(102/100)**2)


def test_explicit_price_scaling_and_byte_sides():
    fixed = tape()
    fixed["price"] = (fixed.price * 1e9).astype("int64")
    fixed["side"] = fixed.side.str.encode("ascii")
    pd.testing.assert_frame_equal(minute_features(tape()), minute_features(fixed, price_type="fixed"))
    with pytest.raises(ValueError):
        normalize_trades(tape(), price_type="guess")


def test_quality_flags_reject_whole_minute_and_duplicate_sequences_preserved():
    frame = tape()
    frame["sequence"] = [1, 1, 1]
    frame.loc[0, "flags"] = 128 | 8
    bars = minute_features(frame)
    assert not bars.iloc[0].feature_eligible
    assert bars.iloc[0][FEATURES].isna().all()
    assert bars.iloc[0].volume == 100
    assert bars.iloc[1].feature_eligible


def test_stable_equal_timestamp_order_and_single_trade_variance():
    frame = tape()
    frame.loc[1, "ts_recv"] = frame.loc[0, "ts_recv"]
    bars = minute_features(frame)
    assert bars.iloc[0].open == 100
    assert bars.iloc[0].close == 102
    assert bars.iloc[1].within_minute_realized_var == 0
    assert bars.iloc[1].size_cv == 0


def test_missing_quality_flags_fail_closed():
    frame = tape()
    frame.loc[0, "flags"] = np.nan
    with pytest.raises((ValueError, TypeError)):
        minute_features(frame)


def test_holdout_refuses_read_without_frozen_comparator():
    with pytest.raises(ValueError, match="existing frozen"):
        build_local(Path("nonexistent.dbn"), Path("none.parquet"), Path("data"),
                    unseal_holdout=True)
