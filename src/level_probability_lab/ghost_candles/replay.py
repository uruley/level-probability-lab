from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from level_probability_lab.exceptions import SessionBoundaryError
from level_probability_lab.ghost_candles.ohlc import (
    is_valid_ohlc,
    repair_ohlc,
    representative_path,
    uncertainty_region,
)
from level_probability_lab.ghost_candles.windows import completed_input_window, future_session_timestamps
from level_probability_lab.time_model import as_utc


def _iso(ts) -> str:
    return as_utc(ts).isoformat()


def _window_payload(window: pd.DataFrame) -> list[dict]:
    rows = []
    for rec in window.itertuples(index=False):
        rows.append(
            {
                "bar_start": _iso(rec.bar_start),
                "open": float(rec.open),
                "high": float(rec.high),
                "low": float(rec.low),
                "close": float(rec.close),
                "volume": float(rec.volume),
            }
        )
    return rows


def run_replay(
    bars: pd.DataFrame,
    forecaster,
    store,
    *,
    lookback: int = 120,
    horizon: int = 5,
    sample_count: int = 50,
    seed: int = 0,
    env_metadata: dict | None = None,
    symbol: str = "QQQ",
) -> list[dict]:
    """Reveal one completed bar at a time and store forecasts before outcomes."""
    ordered = bars.copy()
    ordered["bar_start"] = pd.to_datetime(ordered["bar_start"], utc=True)
    ordered = ordered.sort_values("bar_start").reset_index(drop=True)
    issued: list[dict] = []

    for i in range(lookback - 1, len(ordered) - horizon):
        last = ordered.iloc[i]
        last_start = last["bar_start"]
        revealed = ordered.iloc[: i + 1]
        try:
            window = completed_input_window(revealed, last_start, lookback)
            future_ts = future_session_timestamps(ordered, last_start, horizon)
        except SessionBoundaryError:
            continue

        paths, inference_s = forecaster.forecast_paths(
            window, future_ts, sample_count=sample_count, seed=seed
        )
        paths = np.asarray(paths, dtype=np.float64)
        displayed = representative_path(paths)
        repaired = []
        invalid = 0
        for step in displayed:
            o, h, l, c = (float(x) for x in step[:4])
            if not is_valid_ohlc(o, h, l, c):
                invalid += 1
                o, h, l, c = repair_ohlc(o, h, l, c)
            repaired.append([o, h, l, c])
        band_low, band_high = uncertainty_region(paths)
        forecast_id = f"{symbol}|{_iso(last_start)}|{getattr(forecaster, 'model_name', 'unknown')}|{seed}"
        row = {
            "forecast_id": forecast_id,
            "symbol": symbol,
            "forecast_created_at": datetime.now(timezone.utc).isoformat(),
            "last_input_timestamp": _iso(last_start),
            "target_timestamps": [_iso(ts) for ts in future_ts],
            "input_window": _window_payload(window),
            "model_name": getattr(forecaster, "model_name", "unknown"),
            "model_revision": getattr(forecaster, "model_revision", ""),
            "tokenizer_name": getattr(forecaster, "tokenizer_name", ""),
            "tokenizer_revision": getattr(forecaster, "tokenizer_revision", ""),
            "sample_count": int(sample_count),
            "random_seed": int(seed),
            "sampled_paths": paths[:, :, :4].tolist(),
            "displayed_path": repaired,
            "displayed_path_method": "sample nearest to median close vector",
            "invalid_ohlc_steps": int(invalid),
            "band_low": band_low.tolist(),
            "band_high": band_high.tolist(),
            "inference_time_s": float(inference_s),
            "environment": env_metadata or {},
        }
        extra = getattr(forecaster, "last_meta", None)
        if extra is not None:
            row["analogue_meta"] = extra
        store.put(row)
        issued.append(row)
        if len(issued) == 1 or len(issued) % 25 == 0:
            print(f"  forecast {len(issued)}  last_input={_iso(last_start)}  {float(inference_s):.3f}s")
    return issued
