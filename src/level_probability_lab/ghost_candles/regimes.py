from __future__ import annotations

import pandas as pd

from level_probability_lab.time_model import as_utc


def session_slot(ts) -> str:
    ny = as_utc(ts).tz_convert("America/New_York")
    minutes = int(ny.hour) * 60 + int(ny.minute)
    open_m = 9 * 60 + 30
    if minutes < open_m + 60:
        return "opening_hour"
    if minutes >= 14 * 60:
        return "final_two_hours"
    return "midday"


def tag_origin(origin_ts, window: list[dict]) -> dict:
    closes = [float(b["close"]) for b in window if "close" in b]
    highs = [float(b["high"]) for b in window if "high" in b]
    lows = [float(b["low"]) for b in window if "low" in b]
    lookback_vol = 0.0
    trend_ratio = 0.0
    if len(closes) >= 2:
        rets = pd.Series(closes).pct_change().dropna()
        lookback_vol = float(rets.std()) if len(rets) else 0.0
        span = (max(highs) - min(lows)) if highs and lows else 0.0
        trend_ratio = abs(closes[-1] - closes[0]) / (span + 1e-12)
    vol_regime = "high_vol" if lookback_vol >= 0.0004 else "low_vol"
    path_regime = "trend" if trend_ratio >= 0.5 else "range"
    ny = as_utc(origin_ts).tz_convert("America/New_York")
    return {
        "session_slot": session_slot(origin_ts),
        "vol_regime": vol_regime,
        "path_regime": path_regime,
        "lookback_vol": lookback_vol,
        "trend_ratio": trend_ratio,
        "session_date": str(ny.date()),
    }
