from __future__ import annotations

from pathlib import Path

import pandas as pd


def ohlcv_from_databento_df(frame: pd.DataFrame) -> pd.DataFrame:
    """Map a Databento OHLCV DataFrame to the project's raw observed schema."""
    work = frame.copy()
    if "ts_event" not in work.columns:
        work = work.reset_index()
    if "ts_event" not in work.columns:
        raise ValueError("Databento OHLCV frame has no ts_event column or index")
    work["ts_event"] = pd.to_datetime(work["ts_event"], utc=True)
    needed = ["symbol", "open", "high", "low", "close", "volume"]
    missing = [c for c in needed if c not in work.columns]
    if missing:
        raise ValueError(f"Databento OHLCV frame missing columns: {missing}")
    out = work[["ts_event", "symbol", "open", "high", "low", "close", "volume"]].copy()
    out = out.dropna(subset=["open", "high", "low", "close"])
    for col in ("publisher_id", "instrument_id"):
        out[col] = work[col] if col in work.columns else pd.NA
    return out.sort_values(["symbol", "ts_event"]).reset_index(drop=True)


def ohlcv_from_dbn_file(path: Path) -> pd.DataFrame:
    import databento as db

    store = db.DBNStore.from_file(path)
    return ohlcv_from_databento_df(store.to_df())
