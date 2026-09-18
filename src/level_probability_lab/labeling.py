from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from level_probability_lab.time_model import expected_horizon_starts, horizon_bounds

VALID_CLASSES = ("upper_first", "lower_first", "neither")
QUALITY_STATUSES = ("ambiguous", "incomplete")
ALL_LABELS = VALID_CLASSES + QUALITY_STATUSES


def log_return_vol(closes: np.ndarray) -> float | None:
    closes = np.asarray(closes, dtype=float)
    closes = closes[np.isfinite(closes)]
    if len(closes) < 2:
        return None
    log_ret = np.diff(np.log(closes))
    log_ret = log_ret[np.isfinite(log_ret)]
    if len(log_ret) < 1:
        return None
    vol = float(np.std(log_ret, ddof=1)) if len(log_ret) > 1 else float(np.std(log_ret, ddof=0))
    return vol


def freeze_boundaries(ref: float, vol_scale: float, k_up: float, k_down: float) -> tuple[float, float]:
    return float(ref + k_up * vol_scale), float(ref - k_down * vol_scale)


def classify_future_path(
    future_by_start: dict[pd.Timestamp, pd.Series],
    expected_starts: pd.DatetimeIndex,
    upper: float,
    lower: float,
    session_close: pd.Timestamp,
    horizon_end: pd.Timestamp,
    interval_minutes: int,
) -> tuple[str, str]:
    """Walk elapsed minutes. Never infer tick order inside a bar."""
    if horizon_end > session_close:
        return "incomplete", "horizon_beyond_session"

    for start in expected_starts:
        if start >= session_close:
            return "incomplete", "horizon_beyond_session"
        bar = future_by_start.get(pd.Timestamp(start))
        if bar is None:
            return "incomplete", "missing_horizon_bar"
        status = bar.get("bar_status", "observed")
        if status == "coverage_gap":
            return "incomplete", "coverage_gap"
        if status == "no_trade":
            continue
        if status != "observed":
            return "incomplete", f"unresolved_status:{status}"
        high = bar["high"]
        low = bar["low"]
        if pd.isna(high) or pd.isna(low):
            return "incomplete", "missing_ohlc"
        hit_up = high >= upper
        hit_down = low <= lower
        if hit_up and hit_down:
            return "ambiguous", "same_bar_both_boundaries"
        if hit_up:
            return "upper_first", "upper_touched_first"
        if hit_down:
            return "lower_first", "lower_touched_first"
    return "neither", "no_boundary_touch"


def _lookback_observed(
    session_obs: pd.DataFrame,
    prediction_start: pd.Timestamp,
    lookback_minutes: int,
    interval_minutes: int,
) -> pd.DataFrame:
    lookback_delta = pd.Timedelta(minutes=lookback_minutes)
    window_start = prediction_start - lookback_delta + pd.Timedelta(minutes=interval_minutes)
    mask = (session_obs["bar_start"] >= window_start) & (session_obs["bar_start"] <= prediction_start)
    return session_obs.loc[mask]


def label_symbol_session(
    session: pd.DataFrame,
    *,
    lookback_minutes: int,
    horizon_minutes: int,
    interval_minutes: int,
    min_observed_for_vol: int,
    k_up: float,
    k_down: float,
    session_close: pd.Timestamp,
) -> list[dict[str, Any]]:
    session = session.sort_values("bar_start")
    observed = session[session["bar_status"] == "observed"].copy()
    by_start = {
        pd.Timestamp(rec["bar_start"]): rec
        for rec in session.to_dict(orient="records")
    }
    rows: list[dict[str, Any]] = []

    for pred in observed.itertuples(index=False):
        pred_start = pd.Timestamp(pred.bar_start)
        pred_end = pd.Timestamp(pred.bar_end)
        usable = pd.Timestamp(pred.usable_at)
        horizon_start, horizon_end = horizon_bounds(pred_end, horizon_minutes)
        expected = expected_horizon_starts(pred_end, horizon_minutes, interval_minutes)

        lookback = _lookback_observed(observed, pred_start, lookback_minutes, interval_minutes)
        lookback_starts = lookback["bar_start"]
        record: dict[str, Any] = {
            "symbol": pred.symbol,
            "prediction_bar_start": pred_start,
            "prediction_bar_end": pred_end,
            "prediction_time": usable,
            "horizon_start": horizon_start,
            "horizon_end": horizon_end,
            "session_date": pred.session_date,
            "session_close": session_close,
            "is_early_close": bool(pred.is_early_close),
            "is_synthetic": bool(getattr(pred, "is_synthetic", False)),
            "reference_price": float(pred.close),
            "lookback_bar_count": int(len(lookback)),
            "lookback_first_start": lookback_starts.min() if len(lookback) else pd.NaT,
            "lookback_last_start": lookback_starts.max() if len(lookback) else pd.NaT,
            "vol_scale": np.nan,
            "vol_log": np.nan,
            "upper": np.nan,
            "lower": np.nan,
            "label": "incomplete",
            "is_valid_class": False,
            "reason": "",
        }

        if len(lookback) < min_observed_for_vol:
            record["reason"] = "insufficient_lookback"
            rows.append(record)
            continue

        vol_log = log_return_vol(lookback["close"].to_numpy())
        if vol_log is None or not np.isfinite(vol_log):
            record["reason"] = "vol_undefined"
            rows.append(record)
            continue
        # Express log-return std as a price scale at the frozen reference.
        vol = abs(float(pred.close)) * float(vol_log)
        if vol == 0:
            record["reason"] = "degenerate_boundaries"
            record["vol_scale"] = 0.0
            record["vol_log"] = float(vol_log)
            rows.append(record)
            continue

        upper, lower = freeze_boundaries(float(pred.close), vol, k_up, k_down)
        record["vol_scale"] = vol
        record["vol_log"] = float(vol_log)
        record["upper"] = upper
        record["lower"] = lower
        if upper <= lower:
            record["reason"] = "degenerate_boundaries"
            rows.append(record)
            continue

        label, reason = classify_future_path(
            by_start,
            expected,
            upper,
            lower,
            pd.Timestamp(session_close),
            horizon_end,
            interval_minutes,
        )
        record["label"] = label
        record["reason"] = reason
        record["is_valid_class"] = label in VALID_CLASSES
        rows.append(record)
    return rows


def build_labels(normalized: pd.DataFrame, cfg_get) -> pd.DataFrame:
    target = cfg_get("prediction", "symbol")
    lookback_minutes = int(cfg_get("prediction", "lookback_minutes"))
    horizon_minutes = int(cfg_get("prediction", "horizon_minutes"))
    min_observed_for_vol = int(cfg_get("prediction", "min_observed_for_vol"))
    interval_minutes = int(cfg_get("time", "bar_interval_minutes"))
    k_up = float(cfg_get("boundaries", "k_up"))
    k_down = float(cfg_get("boundaries", "k_down"))

    target_bars = normalized[normalized["symbol"] == target].copy()
    if target_bars.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    grouped = target_bars[target_bars["is_regular_session"]].groupby("session_date", sort=True)
    for session_date, session in grouped:
        if session.empty:
            continue
        session_close = pd.Timestamp(session["session_close"].iloc[0])
        rows.extend(
            label_symbol_session(
                session,
                lookback_minutes=lookback_minutes,
                horizon_minutes=horizon_minutes,
                interval_minutes=interval_minutes,
                min_observed_for_vol=min_observed_for_vol,
                k_up=k_up,
                k_down=k_down,
                session_close=session_close,
            )
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
