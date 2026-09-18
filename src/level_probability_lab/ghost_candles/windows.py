from __future__ import annotations

import pandas as pd

from level_probability_lab.exceptions import SessionBoundaryError
from level_probability_lab.time_model import as_utc


def completed_input_window(
    bars: pd.DataFrame,
    last_bar_start,
    lookback: int,
) -> pd.DataFrame:
    """Last `lookback` completed bars at or before last_bar_start. No future rows."""
    if lookback < 1:
        raise SessionBoundaryError("lookback must be >= 1")
    last = as_utc(last_bar_start)
    work = bars.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    available = work.loc[work["bar_start"] <= last].sort_values("bar_start")
    if last not in set(available["bar_start"]):
        raise SessionBoundaryError(f"last_bar_start {last} is not in the revealed bars")
    if len(available) < lookback:
        raise SessionBoundaryError(f"need {lookback} completed bars, have {len(available)}")
    window = available.tail(lookback).reset_index(drop=True)
    if as_utc(window.iloc[-1]["bar_start"]) != last:
        raise SessionBoundaryError("input window does not end at last_bar_start")
    starts = window["bar_start"]
    deltas = starts.diff().dropna()
    if not (deltas == pd.Timedelta(minutes=1)).all():
        raise SessionBoundaryError("lookback is not contiguous one-minute bars")
    return window


def future_session_timestamps(
    bars: pd.DataFrame,
    last_bar_start,
    horizon: int,
) -> pd.DatetimeIndex:
    """Exactly `horizon` chronological regular-session minutes after last_bar_start."""
    if horizon < 1:
        raise SessionBoundaryError("horizon must be >= 1")
    last = as_utc(last_bar_start)
    work = bars.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    match = work.loc[work["bar_start"] == last]
    if match.empty:
        raise SessionBoundaryError(f"last_bar_start {last} not found")
    session_close = as_utc(match.iloc[0]["session_close"])
    candidates = pd.date_range(last + pd.Timedelta(minutes=1), periods=horizon, freq="1min", tz="UTC")
    if any(ts >= session_close for ts in candidates):
        raise SessionBoundaryError("forecast would cross the regular-session close")
    if len(candidates) != horizon:
        raise SessionBoundaryError("could not produce the requested horizon timestamps")
    return candidates
