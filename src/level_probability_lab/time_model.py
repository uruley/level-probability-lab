from __future__ import annotations

import pandas as pd


def as_utc(ts: pd.Timestamp | str) -> pd.Timestamp:
    value = pd.Timestamp(ts)
    if value.tzinfo is None:
        return value.tz_localize("UTC")
    return value.tz_convert("UTC")


def bar_end(bar_start: pd.Timestamp, interval_minutes: int = 1) -> pd.Timestamp:
    return as_utc(bar_start) + pd.Timedelta(minutes=interval_minutes)


def usable_at(
    bar_start: pd.Timestamp,
    interval_minutes: int = 1,
    publication_lag_seconds: int = 0,
) -> pd.Timestamp:
    """Time the bar is treated as an input.

    Databento OHLCV `ts_event` is the inclusive start of the bar. The bar is
    complete at `bar_end`. `publication_lag_seconds` is an assumed lag, not a
    historical exchange publication timestamp.
    """
    return bar_end(bar_start, interval_minutes) + pd.Timedelta(seconds=publication_lag_seconds)


def horizon_bounds(completed_bar_end: pd.Timestamp, horizon_minutes: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = as_utc(completed_bar_end)
    return start, start + pd.Timedelta(minutes=horizon_minutes)


def expected_horizon_starts(
    completed_bar_end: pd.Timestamp,
    horizon_minutes: int,
    interval_minutes: int = 1,
) -> pd.DatetimeIndex:
    start, end = horizon_bounds(completed_bar_end, horizon_minutes)
    return pd.date_range(start, end, freq=f"{interval_minutes}min", inclusive="left", tz="UTC")


def attach_time_columns(
    frame: pd.DataFrame,
    start_col: str = "bar_start",
    interval_minutes: int = 1,
    publication_lag_seconds: int = 0,
) -> pd.DataFrame:
    out = frame.copy()
    out[start_col] = pd.to_datetime(out[start_col], utc=True)
    out["bar_end"] = out[start_col] + pd.Timedelta(minutes=interval_minutes)
    out["usable_at"] = out["bar_end"] + pd.Timedelta(seconds=publication_lag_seconds)
    return out
