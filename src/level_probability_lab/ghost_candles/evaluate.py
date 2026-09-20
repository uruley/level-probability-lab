from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.ghost_candles.direction import directional_hit, move_sign
from level_probability_lab.ghost_candles.distribution import sample_horizon_stats
from level_probability_lab.ghost_candles.regimes import tag_origin
from level_probability_lab.time_model import as_utc


def score_engine(forecasts: list[dict], bars: pd.DataFrame, engine: str) -> pd.DataFrame:
    work = bars.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    by_start = work.set_index("bar_start").sort_index()
    rows: list[dict] = []
    for forecast in forecasts:
        origin_ts = as_utc(forecast["last_input_timestamp"])
        origin_close = float(forecast["input_window"][-1]["close"])
        targets = [as_utc(ts) for ts in forecast["target_timestamps"]]
        paths = np.asarray(forecast["sampled_paths"], dtype=np.float64)
        if paths.ndim != 3:
            paths = paths.reshape(1, len(targets), 4)
        stats = sample_horizon_stats(paths, origin_close)
        displayed = forecast.get("displayed_path") or []
        window = forecast.get("input_window") or []
        tags = tag_origin(origin_ts, window)
        for h_idx, ts in enumerate(targets):
            if ts not in by_start.index:
                continue
            actual = by_start.loc[ts]
            act_c = float(actual["close"])
            act_h = float(actual["high"])
            act_l = float(actual["low"])
            st = stats[h_idx]
            median_c = st["median_close"]
            stance = move_sign(median_c, origin_close)
            hit = directional_hit(median_c, act_c, origin_close)
            p_up = st["p_close_gt_origin"]
            p_dn = st["p_close_lt_origin"]
            weighted = (forecast.get("analogue_meta") or {}).get("weighted_p_close_gt_origin")
            if weighted is not None and h_idx < len(weighted):
                p_up = float(weighted[h_idx])
                p_dn = float(max(0.0, min(1.0, 1.0 - p_up)))
            y_up = int(act_c > origin_close)
            y_dn = int(act_c < origin_close)
            is_persist = engine == "persistence"
            p_clip = min(max(float(p_up), 1e-6), 1.0 - 1e-6)
            row = {
                "engine": engine,
                "forecast_id": forecast.get("forecast_id"),
                "session_date": str(forecast.get("session_date") or tags.get("session_date")),
                "origin_timestamp": origin_ts.isoformat(),
                "horizon_minutes": h_idx + 1,
                "target_timestamp": ts.isoformat(),
                "origin_close": origin_close,
                "actual_close": act_c,
                "actual_high": act_h,
                "actual_low": act_l,
                "subsequent_return": (act_c / origin_close - 1.0) if origin_close else np.nan,
                "median_close": median_c,
                "median_close_abs_error": abs(median_c - act_c),
                "displayed_close_abs_error": (
                    abs(float(displayed[h_idx][3]) - act_c) if h_idx < len(displayed) else np.nan
                ),
                "stance": stance,
                "directional_hit": hit if hit is not None else np.nan,
                "p_close_gt_origin": np.nan if is_persist else p_up,
                "p_close_lt_origin": np.nan if is_persist else p_dn,
                "brier_up": np.nan if is_persist else (p_up - y_up) ** 2,
                "brier_down": np.nan if is_persist else (p_dn - y_dn) ** 2,
                "log_loss_up": np.nan if is_persist else float(-(y_up * np.log(p_clip) + (1 - y_up) * np.log(1 - p_clip))),
                "actual_up": y_up,
                "close_q10": st.get("close_q10"),
                "close_q90": st.get("close_q90"),
                "high_q90": st.get("high_q90"),
                "low_q10": st.get("low_q10"),
                "range_q50": st.get("range_q50"),
                "max_upside_q50": st.get("max_upside_q50"),
                "max_downside_q50": st.get("max_downside_q50"),
                "actual_in_close_q10_q90": int(st.get("close_q10") <= act_c <= st.get("close_q90")),
                "inference_time_s": float(forecast.get("inference_time_s") or 0.0),
                **tags,
            }
            rows.append(row)
    return pd.DataFrame(rows)
