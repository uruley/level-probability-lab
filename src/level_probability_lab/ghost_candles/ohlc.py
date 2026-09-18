from __future__ import annotations

import numpy as np


def is_valid_ohlc(open_: float, high: float, low: float, close: float) -> bool:
    if any(v != v for v in (open_, high, low, close)):  # NaN
        return False
    return high >= max(open_, close) and low <= min(open_, close) and high >= low


def repair_ohlc(open_: float, high: float, low: float, close: float) -> tuple[float, float, float, float]:
    high_r = max(high, open_, close)
    low_r = min(low, open_, close)
    if high_r < low_r:
        high_r, low_r = low_r, high_r
    return float(open_), float(high_r), float(low_r), float(close)


def representative_path(paths: np.ndarray) -> np.ndarray:
    """Pick one real sampled path nearest the median close vector.

    Averaging open/high/low/close independently can yield invalid candles
    (high < open, etc.). Selecting an actual path preserves OHLC structure.
    """
    arr = np.asarray(paths, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[-1] < 4:
        raise ValueError(f"expected (samples, horizon, 4+) OHLC paths, got {arr.shape}")
    closes = arr[:, :, 3]
    median = np.median(closes, axis=0)
    dist = np.abs(closes - median).sum(axis=1)
    return arr[int(np.argmin(dist))].copy()


def uncertainty_region(
    paths: np.ndarray,
    low_q: float = 0.1,
    high_q: float = 0.9,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-horizon low/high envelope from sampled path lows and highs."""
    arr = np.asarray(paths, dtype=np.float64)
    low = np.quantile(arr[:, :, 2], low_q, axis=0)
    high = np.quantile(arr[:, :, 1], high_q, axis=0)
    return low, high
