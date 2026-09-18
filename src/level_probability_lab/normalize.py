from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.calendar import annotate_session_flags, expected_regular_minutes, session_schedule
from level_probability_lab.time_model import attach_time_columns


PRICE_COLS = ["open", "high", "low", "close"]


def raw_to_observed(
    raw: pd.DataFrame,
    *,
    interval_minutes: int,
    publication_lag_seconds: int,
    source_dataset: str,
    source_schema: str,
    is_synthetic: bool,
) -> pd.DataFrame:
    """Map provider/synthetic raw OHLCV to observed bars. Does not fill gaps."""
    if raw.empty:
        return raw.copy()
    frame = raw.copy()
    if "bar_start" not in frame.columns:
        if "ts_event" in frame.columns:
            frame["bar_start"] = frame["ts_event"]
        elif isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.reset_index()
            first = frame.columns[0]
            frame = frame.rename(columns={first: "bar_start"})
        else:
            raise ValueError("raw data needs bar_start or ts_event")
    frame["bar_start"] = pd.to_datetime(frame["bar_start"], utc=True)
    frame = attach_time_columns(
        frame,
        interval_minutes=interval_minutes,
        publication_lag_seconds=publication_lag_seconds,
    )
    frame["bar_status"] = "observed"
    frame["source_dataset"] = source_dataset
    frame["source_schema"] = source_schema
    frame["is_synthetic"] = bool(is_synthetic)
    if "publisher_id" not in frame.columns:
        frame["publisher_id"] = pd.NA
    if "instrument_id" not in frame.columns:
        frame["instrument_id"] = pd.NA
    keep = [
        "symbol",
        "bar_start",
        "bar_end",
        "usable_at",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "publisher_id",
        "instrument_id",
        "bar_status",
        "source_dataset",
        "source_schema",
        "is_synthetic",
    ]
    return frame[keep].sort_values(["symbol", "bar_start"]).reset_index(drop=True)


def _status_for_missing_runs(n_missing: int, max_no_trade_gap_minutes: int, interval_minutes: int) -> str:
    gap_minutes = n_missing * interval_minutes
    if gap_minutes <= max_no_trade_gap_minutes:
        return "no_trade"
    return "coverage_gap"


def expand_session_grid(
    observed: pd.DataFrame,
    schedule: pd.DataFrame,
    *,
    interval_minutes: int,
    max_no_trade_gap_minutes: int,
    calendar_name: str,
) -> pd.DataFrame:
    """Insert no_trade / coverage_gap placeholders. Never invents OHLC."""
    if observed.empty:
        return observed.copy()

    frames: list[pd.DataFrame] = []
    expected = expected_regular_minutes(schedule, interval_minutes)
    for symbol, grp in observed.groupby("symbol", sort=False):
        obs = grp.drop_duplicates(subset=["bar_start"]).set_index("bar_start").sort_index()
        template = pd.DataFrame(index=expected)
        template.index.name = "bar_start"
        aligned = template.join(obs, how="left")
        missing = aligned["close"].isna()
        statuses = pd.Series("observed", index=aligned.index, dtype="object")
        statuses.loc[missing] = "no_trade"

        if missing.any():
            run_id = missing.ne(missing.shift(fill_value=False)).cumsum()
            for _, run in missing[missing].groupby(run_id[missing]):
                status = _status_for_missing_runs(len(run), max_no_trade_gap_minutes, interval_minutes)
                statuses.loc[run.index] = status

        aligned["bar_status"] = statuses.values
        aligned["symbol"] = symbol
        for col in PRICE_COLS:
            if col in aligned.columns:
                aligned.loc[aligned["bar_status"] != "observed", col] = np.nan
        aligned.loc[aligned["bar_status"] != "observed", "volume"] = 0
        aligned = aligned.reset_index()
        # Restore time columns for placeholders.
        interval = pd.Timedelta(minutes=interval_minutes)
        aligned["bar_end"] = aligned["bar_start"] + interval
        if "usable_at" in grp.columns and len(grp):
            lag = grp["usable_at"].iloc[0] - grp["bar_end"].iloc[0]
        else:
            lag = pd.Timedelta(0)
        aligned["usable_at"] = aligned["bar_end"] + lag
        for col in ("source_dataset", "source_schema", "is_synthetic"):
            if col in grp.columns:
                aligned[col] = grp[col].iloc[0]
        frames.append(aligned)

    out = pd.concat(frames, ignore_index=True)
    out = annotate_session_flags(out, schedule, calendar_name=calendar_name)
    return out.sort_values(["symbol", "bar_start"]).reset_index(drop=True)


def flag_discontinuities(frame: pd.DataFrame, log_return_threshold: float) -> pd.DataFrame:
    """Flag large overnight open/prev_close moves. Prices remain unadjusted."""
    out = frame.copy()
    out["discontinuity_candidate"] = False
    if out.empty:
        return out
    observed = out["bar_status"] == "observed"
    for symbol, idx in out.groupby("symbol").groups.items():
        loc = list(idx)
        sub = out.loc[loc]
        sess = sub["session_date"]
        prev_close = sub["close"].where(observed.loc[loc]).ffill()
        session_changed = sess.ne(sess.shift())
        first_obs = observed.loc[loc] & session_changed
        prev = prev_close.shift(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            move = np.log(sub["open"] / prev)
        flag = first_obs & move.abs().gt(log_return_threshold)
        out.loc[sub.index[flag.fillna(False)], "discontinuity_candidate"] = True
    return out


def normalize_ohlcv(
    raw: pd.DataFrame,
    *,
    calendar_name: str,
    interval_minutes: int,
    publication_lag_seconds: int,
    max_no_trade_gap_minutes: int,
    discontinuity_log_return: float,
    source_dataset: str,
    source_schema: str,
    is_synthetic: bool,
) -> pd.DataFrame:
    observed = raw_to_observed(
        raw,
        interval_minutes=interval_minutes,
        publication_lag_seconds=publication_lag_seconds,
        source_dataset=source_dataset,
        source_schema=source_schema,
        is_synthetic=is_synthetic,
    )
    start = observed["bar_start"].min()
    end = observed["bar_start"].max()
    schedule = session_schedule(start, end, calendar_name=calendar_name)
    expanded = expand_session_grid(
        observed,
        schedule,
        interval_minutes=interval_minutes,
        max_no_trade_gap_minutes=max_no_trade_gap_minutes,
        calendar_name=calendar_name,
    )
    return flag_discontinuities(expanded, discontinuity_log_return)
