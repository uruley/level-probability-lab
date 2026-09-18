from __future__ import annotations

import pandas as pd


def join_context(
    labels: pd.DataFrame,
    normalized: pd.DataFrame,
    context_symbol: str,
    stale_seconds: int,
    prefix: str = "context",
) -> pd.DataFrame:
    """Attach the last completed context bar available at prediction time.

    No future interpolation. Missing or stale context is flagged, not filled.
    """
    if labels.empty:
        return labels.copy()
    out = labels.copy()
    col_start = f"{prefix}_bar_start"
    col_usable = f"{prefix}_usable_at"
    col_close = f"{prefix}_close"
    col_volume = f"{prefix}_volume"
    col_symbol = f"{prefix}_symbol"
    col_stale_s = f"{prefix}_staleness_seconds"
    col_stale = f"{prefix}_stale"
    ctx = normalized[
        (normalized["symbol"] == context_symbol) & (normalized["bar_status"] == "observed")
    ][["bar_start", "usable_at", "close", "volume"]].sort_values("usable_at")
    ctx = ctx.rename(
        columns={
            "bar_start": col_start,
            "usable_at": col_usable,
            "close": col_close,
            "volume": col_volume,
        }
    )
    left = out.sort_values("prediction_time")
    if ctx.empty:
        left[col_symbol] = context_symbol
        left[col_start] = pd.NaT
        left[col_usable] = pd.NaT
        left[col_close] = pd.NA
        left[col_volume] = pd.NA
        left[col_stale_s] = pd.NA
        left[col_stale] = True
        return left

    merged = pd.merge_asof(
        left,
        ctx,
        left_on="prediction_time",
        right_on=col_usable,
        direction="backward",
    )
    merged[col_symbol] = context_symbol
    merged[col_stale_s] = (merged["prediction_time"] - merged[col_usable]).dt.total_seconds()
    merged[col_stale] = merged[col_usable].isna() | (merged[col_stale_s] > stale_seconds)
    future_leak = merged[col_usable].notna() & (merged[col_usable] > merged["prediction_time"])
    if future_leak.any():
        raise RuntimeError("context join leaked future bars")
    return merged
