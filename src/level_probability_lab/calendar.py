from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as mcal

from level_probability_lab.time_model import as_utc


@lru_cache(maxsize=8)
def get_calendar(name: str = "NYSE"):
    return mcal.get_calendar(name)


def session_schedule(start, end, calendar_name: str = "NYSE") -> pd.DataFrame:
    cal = get_calendar(calendar_name)
    start_date = pd.Timestamp(start).tz_localize(None).date() if pd.Timestamp(start).tzinfo else pd.Timestamp(start).date()
    end_date = pd.Timestamp(end).tz_localize(None).date() if pd.Timestamp(end).tzinfo else pd.Timestamp(end).date()
    schedule = cal.schedule(start_date=str(start_date), end_date=str(end_date))
    if schedule.empty:
        return schedule
    out = schedule.copy()
    out["market_open"] = pd.to_datetime(out["market_open"], utc=True)
    out["market_close"] = pd.to_datetime(out["market_close"], utc=True)
    return out


def early_close_session_dates(schedule: pd.DataFrame, calendar_name: str = "NYSE") -> set[date]:
    if schedule.empty:
        return set()
    cal = get_calendar(calendar_name)
    early = cal.early_closes(schedule)
    if early is None or len(early) == 0:
        return set()
    dates: set[date] = set()
    for idx in early.index:
        ts = pd.Timestamp(idx)
        dates.add(ts.tz_localize(None).date() if ts.tzinfo else ts.date())
    return dates


def session_date_of(ts: pd.Timestamp) -> date:
    ts = as_utc(ts)
    naive = ts.tz_convert("America/New_York").tz_localize(None)
    return naive.date()


def session_minute_index(
    market_open: pd.Timestamp,
    market_close: pd.Timestamp,
    interval_minutes: int = 1,
) -> pd.DatetimeIndex:
    return pd.date_range(
        as_utc(market_open),
        as_utc(market_close),
        freq=f"{interval_minutes}min",
        inclusive="left",
        tz="UTC",
    )


def expected_regular_minutes(schedule: pd.DataFrame, interval_minutes: int = 1) -> pd.DatetimeIndex:
    parts = [
        session_minute_index(row.market_open, row.market_close, interval_minutes)
        for row in schedule.itertuples()
    ]
    if not parts:
        return pd.DatetimeIndex([], tz="UTC")
    stamps: list[pd.Timestamp] = []
    for part in parts:
        stamps.extend(part.tolist())
    return pd.DatetimeIndex(stamps, tz="UTC")


def annotate_session_flags(
    frame: pd.DataFrame,
    schedule: pd.DataFrame,
    calendar_name: str = "NYSE",
    start_col: str = "bar_start",
) -> pd.DataFrame:
    """Flag regular-session membership using the exchange calendar.

    Bars are regular-session if market_open <= bar_start < market_close.
    """
    out = frame.copy()
    out[start_col] = pd.to_datetime(out[start_col], utc=True)
    out["is_regular_session"] = False
    out["is_early_close"] = False
    out["session_date"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")
    out["session_open"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    out["session_close"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    if schedule.empty or out.empty:
        return out

    early_dates = early_close_session_dates(schedule, calendar_name)
    starts = out[start_col]
    for idx, row in schedule.iterrows():
        ts = pd.Timestamp(idx)
        sess_date = ts.tz_localize(None).date() if ts.tzinfo else ts.date()
        mask = (starts >= row.market_open) & (starts < row.market_close)
        if not mask.any():
            continue
        out.loc[mask, "is_regular_session"] = True
        out.loc[mask, "session_date"] = pd.Timestamp(sess_date)
        out.loc[mask, "session_open"] = row.market_open
        out.loc[mask, "session_close"] = row.market_close
        out.loc[mask, "is_early_close"] = sess_date in early_dates
    return out
