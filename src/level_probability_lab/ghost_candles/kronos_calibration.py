"""Post-hoc Kronos interval calibration. No Kronos weight updates."""

from __future__ import annotations

import numpy as np
import pandas as pd


def scaled_interval(median: np.ndarray, q10: np.ndarray, q90: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    lo = median - float(scale) * (median - q10)
    hi = median + float(scale) * (q90 - median)
    return lo, hi


def interval_coverage(actual: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((actual >= lo) & (actual <= hi)))


def fit_interval_scale(
    frame: pd.DataFrame,
    *,
    target_coverage: float = 0.80,
    max_scale: float = 8.0,
) -> float:
    """Coverage-matching inflation of the q10–q90 band around the median.

    Fit on development rows only. scale>=1 widens an undercovering interval.
    """
    work = frame.dropna(subset=["actual_close", "median_close", "close_q10", "close_q90"])
    actual = work["actual_close"].to_numpy(dtype=np.float64)
    median = work["median_close"].to_numpy(dtype=np.float64)
    q10 = work["close_q10"].to_numpy(dtype=np.float64)
    q90 = work["close_q90"].to_numpy(dtype=np.float64)
    if actual.size == 0:
        return 1.0
    lo_s, hi_s = 1.0, float(max_scale)
    best = 1.0
    for _ in range(24):
        mid = 0.5 * (lo_s + hi_s)
        lo, hi = scaled_interval(median, q10, q90, mid)
        cov = interval_coverage(actual, lo, hi)
        best = mid
        if cov < target_coverage:
            lo_s = mid
        else:
            hi_s = mid
    return float(best)


def apply_interval_scale(frame: pd.DataFrame, scale: float) -> pd.DataFrame:
    out = frame.copy()
    lo, hi = scaled_interval(
        out["median_close"].to_numpy(dtype=np.float64),
        out["close_q10"].to_numpy(dtype=np.float64),
        out["close_q90"].to_numpy(dtype=np.float64),
        scale,
    )
    out = out.copy()
    out["close_q10_calibrated"] = lo
    out["close_q90_calibrated"] = hi
    out["interval_scale"] = float(scale)
    out["actual_in_calibrated_q10_q90"] = ((out["actual_close"] >= lo) & (out["actual_close"] <= hi)).astype(int)
    return out
