from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.time_model import as_utc


def persistence_recent_range_baseline(
    last_close: float,
    recent_ranges: list[float],
    horizon: int,
) -> list[list[float]]:
    """Flat close at last close, range = median of recent (high-low).

    Produces valid OHLC dojis. Same timestamps as the Kronos forecast.
    """
    if not recent_ranges:
        half = 0.0
    else:
        half = float(np.median(recent_ranges)) / 2.0
    candles = []
    for _ in range(horizon):
        o = float(last_close)
        c = float(last_close)
        h = o + half
        l = o - half
        candles.append([o, h, l, c])
    return candles


def _direction(move_to: float, origin: float) -> int:
    if move_to > origin:
        return 1
    if move_to < origin:
        return -1
    return 0


def score_forecasts(forecasts: list[dict], bars: pd.DataFrame) -> pd.DataFrame:
    work = bars.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    by_start = work.set_index("bar_start").sort_index()
    rows: list[dict] = []
    for forecast in forecasts:
        last_ts = as_utc(forecast["last_input_timestamp"])
        last_close = float(forecast["input_window"][-1]["close"])
        recent_ranges = [
            float(b["high"]) - float(b["low"])
            for b in forecast["input_window"]
            if "high" in b and "low" in b
        ]
        targets = [as_utc(ts) for ts in forecast["target_timestamps"]]
        displayed = forecast["displayed_path"]
        baseline = persistence_recent_range_baseline(last_close, recent_ranges, len(targets))
        for h_idx, ts in enumerate(targets):
            if ts not in by_start.index:
                continue
            actual = by_start.loc[ts]
            pred = displayed[h_idx]
            base = baseline[h_idx]
            pred_o, pred_h, pred_l, pred_c = (float(x) for x in pred[:4])
            base_o, base_h, base_l, base_c = (float(x) for x in base[:4])
            act_o, act_h, act_l, act_c = (
                float(actual["open"]),
                float(actual["high"]),
                float(actual["low"]),
                float(actual["close"]),
            )
            rows.append(
                {
                    "forecast_id": forecast["forecast_id"],
                    "horizon_minutes": h_idx + 1,
                    "target_timestamp": ts.isoformat(),
                    "kronos_open_abs_error": abs(pred_o - act_o),
                    "kronos_high_abs_error": abs(pred_h - act_h),
                    "kronos_low_abs_error": abs(pred_l - act_l),
                    "kronos_close_abs_error": abs(pred_c - act_c),
                    "kronos_range_error": abs((pred_h - pred_l) - (act_h - act_l)),
                    "kronos_direction_hit": int(_direction(pred_c, last_close) == _direction(act_c, last_close)),
                    "baseline_open_abs_error": abs(base_o - act_o),
                    "baseline_high_abs_error": abs(base_h - act_h),
                    "baseline_low_abs_error": abs(base_l - act_l),
                    "baseline_close_abs_error": abs(base_c - act_c),
                    "baseline_range_error": abs((base_h - base_l) - (act_h - act_l)),
                    "baseline_direction_hit": int(_direction(base_c, last_close) == _direction(act_c, last_close)),
                    "inference_time_s": float(forecast.get("inference_time_s") or 0.0),
                }
            )
    return pd.DataFrame(rows)
