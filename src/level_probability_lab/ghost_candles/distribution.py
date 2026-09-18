from __future__ import annotations

import numpy as np

DEFAULT_QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def sample_horizon_stats(
    paths: np.ndarray,
    origin_close: float,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
) -> list[dict]:
    """Per-horizon statistics over the FULL sample set (not the displayed path)."""
    arr = np.asarray(paths, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[-1] < 4:
        raise ValueError(f"expected (samples, horizon, 4+) paths, got {arr.shape}")
    origin = float(origin_close)
    closes = arr[:, :, 3]
    highs = arr[:, :, 1]
    lows = arr[:, :, 2]
    ranges = highs - lows
    rows: list[dict] = []
    for h in range(arr.shape[1]):
        c = closes[:, h]
        hi = highs[:, h]
        lo = lows[:, h]
        rg = ranges[:, h]
        upside = (highs[:, : h + 1] - origin).max(axis=1)
        downside = (lows[:, : h + 1] - origin).min(axis=1)
        row = {
            "horizon_minutes": h + 1,
            "median_close": float(np.median(c)),
            "p_close_gt_origin": float(np.mean(c > origin)),
            "p_close_lt_origin": float(np.mean(c < origin)),
            "range_q50": float(np.median(rg)),
            "max_upside_q50": float(np.median(upside)),
            "max_downside_q50": float(np.median(downside)),
        }
        for q in quantiles:
            tag = f"q{int(round(q * 100))}"
            row[f"close_{tag}"] = float(np.quantile(c, q))
            row[f"high_{tag}"] = float(np.quantile(hi, q))
            row[f"low_{tag}"] = float(np.quantile(lo, q))
            row[f"range_{tag}"] = float(np.quantile(rg, q))
        rows.append(row)
    return rows
