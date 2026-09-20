"""Probability scoring with session-blocked uncertainty.

Overlapping minute forecasts are not treated as independent draws.
Paper testing only.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

P_CLIP = 1e-6
DEFAULT_P_EDGES = (0.0, 0.40, 0.45, 0.55, 0.60, 0.70, 1.0000001)
MIN_BIN_COUNT = 30


def clip_p(p: np.ndarray | float) -> np.ndarray | float:
    return np.clip(p, P_CLIP, 1.0 - P_CLIP)


def brier_score(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.float64)
    p = clip_p(np.asarray(p, dtype=np.float64))
    if y.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.float64)
    p = clip_p(np.asarray(p, dtype=np.float64))
    if y.size == 0:
        return float("nan")
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def brier_skill_score(y: np.ndarray, p: np.ndarray, p_clim: float) -> float:
    bs = brier_score(y, p)
    bs_ref = brier_score(y, np.full_like(y, float(p_clim), dtype=np.float64))
    if not np.isfinite(bs) or not np.isfinite(bs_ref) or bs_ref == 0:
        return float("nan")
    return float(1.0 - bs / bs_ref)


def calibration_slope_intercept(y: np.ndarray, p: np.ndarray) -> dict[str, float | None]:
    """OLS of y on p. Reported only when there is variation in p."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    n = int(y.size)
    if n < 10 or float(np.std(p)) < 1e-12:
        return {"n": n, "slope": None, "intercept": None, "r2": None}
    x = np.column_stack([np.ones(n), p])
    try:
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    except np.linalg.LinAlgError:
        return {"n": n, "slope": None, "intercept": None, "r2": None}
    intercept, slope = float(coef[0]), float(coef[1])
    pred = intercept + slope * p
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = None if ss_tot <= 0 else float(1.0 - ss_res / ss_tot)
    return {"n": n, "slope": slope, "intercept": intercept, "r2": r2}


def _adaptive_edges(p: np.ndarray, edges: Sequence[float], min_count: int) -> np.ndarray:
    edges = np.asarray(edges, dtype=np.float64)
    if p.size == 0:
        return edges
    counts, _ = np.histogram(p, bins=edges)
    if counts.size == 0 or int(np.min(counts[counts > 0], initial=min_count)) >= min_count:
        return edges
    # Merge left-to-right until each kept interior bin meets min_count (last bin may stay small).
    merged = [float(edges[0])]
    running = 0
    for i, count in enumerate(counts):
        running += int(count)
        is_last = i == len(counts) - 1
        if running >= min_count or is_last:
            merged.append(float(edges[i + 1]))
            running = 0
    if len(merged) < 2:
        return edges
    return np.asarray(merged, dtype=np.float64)


def reliability_table(
    y: np.ndarray,
    p: np.ndarray,
    returns: np.ndarray | None = None,
    edges: Sequence[float] = DEFAULT_P_EDGES,
    min_count: int = MIN_BIN_COUNT,
) -> list[dict[str, Any]]:
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    if returns is None:
        returns = np.full_like(p, np.nan)
    returns = np.asarray(returns, dtype=np.float64)
    bins = _adaptive_edges(p, edges, min_count)
    rows: list[dict[str, Any]] = []
    for i in range(len(bins) - 1):
        lo, hi = float(bins[i]), float(bins[i + 1])
        if i == len(bins) - 2:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        yy, pp, rr = y[mask], p[mask], returns[mask]
        finite_r = rr[np.isfinite(rr)]
        rows.append(
            {
                "bin_lo": lo,
                "bin_hi": hi,
                "n": n,
                "predicted_mean_p": float(pp.mean()),
                "actual_event_rate": float(yy.mean()),
                "mean_subsequent_return": float(finite_r.mean()) if finite_r.size else None,
                "median_subsequent_return": float(np.median(finite_r)) if finite_r.size else None,
                "return_p10": float(np.quantile(finite_r, 0.1)) if finite_r.size else None,
                "return_p90": float(np.quantile(finite_r, 0.9)) if finite_r.size else None,
                "extreme_vs_half": bool(lo >= 0.60 or hi <= 0.40),
            }
        )
    return rows


def session_blocked_metrics(
    frame: pd.DataFrame,
    *,
    p_col: str = "p_close_gt_origin",
    y_col: str = "actual_up",
    session_col: str = "session_date",
    p_clim: float,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    work = frame.dropna(subset=[p_col, y_col, session_col]).copy()
    if work.empty:
        return {"n": 0, "n_sessions": 0}
    y = work[y_col].to_numpy(dtype=np.float64)
    p = work[p_col].to_numpy(dtype=np.float64)
    sessions = work[session_col].astype(str).to_numpy()
    unique = np.unique(sessions)
    session_rows: list[dict[str, Any]] = []
    for sess in unique:
        mask = sessions == sess
        yy, pp = y[mask], p[mask]
        session_rows.append(
            {
                "session_date": str(sess),
                "n": int(mask.sum()),
                "brier": brier_score(yy, pp),
                "log_loss": log_loss(yy, pp),
                "bss_vs_climatology": brier_skill_score(yy, pp, p_clim),
                "event_rate": float(yy.mean()),
                "mean_p": float(pp.mean()),
            }
        )
    sess_brier = np.array([r["brier"] for r in session_rows], dtype=np.float64)
    rng = np.random.default_rng(seed)
    boot = []
    if len(unique) >= 2 and n_bootstrap > 0:
        for _ in range(n_bootstrap):
            draw = rng.choice(unique, size=len(unique), replace=True)
            # concatenate minutes belonging to drawn sessions (dependence preserved within session)
            parts_y = [y[sessions == s] for s in draw]
            parts_p = [p[sessions == s] for s in draw]
            yy = np.concatenate(parts_y)
            pp = np.concatenate(parts_p)
            boot.append(
                (
                    brier_score(yy, pp),
                    log_loss(yy, pp),
                    brier_skill_score(yy, pp, p_clim),
                )
            )
    boot_arr = np.asarray(boot, dtype=np.float64) if boot else np.zeros((0, 3))

    def _ci(col: int) -> dict[str, float | None]:
        if boot_arr.size == 0:
            return {"lo": None, "hi": None}
        return {
            "lo": float(np.quantile(boot_arr[:, col], 0.025)),
            "hi": float(np.quantile(boot_arr[:, col], 0.975)),
        }

    cal = calibration_slope_intercept(y, p)
    returns = None
    if "subsequent_return" in work.columns:
        returns = work["subsequent_return"].to_numpy(dtype=np.float64)
    return {
        "n": int(len(work)),
        "n_sessions": int(len(unique)),
        "independence_note": "bootstrap resamples sessions, not overlapping minutes",
        "climatology_p": float(p_clim),
        "brier": brier_score(y, p),
        "log_loss": log_loss(y, p),
        "bss_vs_climatology": brier_skill_score(y, p, p_clim),
        "brier_session_mean": float(np.mean(sess_brier)),
        "brier_session_se": float(np.std(sess_brier, ddof=1) / np.sqrt(len(sess_brier))) if len(sess_brier) > 1 else None,
        "brier_session_bootstrap_95": _ci(0),
        "log_loss_session_bootstrap_95": _ci(1),
        "bss_session_bootstrap_95": _ci(2),
        "calibration": cal,
        "reliability": reliability_table(y, p, returns),
        "by_session": session_rows,
    }


def train_climatology(
    history: pd.DataFrame,
    *,
    horizon: int = 5,
    last_session: str = "2023-12-29",
) -> dict[int, float]:
    """Unconditional P(close_{t+h} > close_t) on completed train sessions only."""
    work = history.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    work["session_date"] = pd.to_datetime(work["session_date"]).dt.strftime("%Y-%m-%d")
    work = work.loc[work["session_date"] <= last_session]
    hits = {h: [0, 0] for h in range(1, horizon + 1)}
    for _, grp in work.groupby("session_date", sort=False):
        grp = grp.sort_values("bar_start")
        closes = grp["close"].to_numpy(dtype=np.float64)
        starts = pd.to_datetime(grp["bar_start"], utc=True).to_numpy(dtype="datetime64[ns]")
        if len(closes) < horizon + 1:
            continue
        links = np.diff(starts).astype("timedelta64[s]").astype(np.int64) == 60
        for h in range(1, horizon + 1):
            if len(closes) <= h:
                continue
            contiguous = np.convolve(links.astype(np.int8), np.ones(h, dtype=np.int8), mode="valid") == h
            y = closes[h:] > closes[:-h]
            hits[h][0] += int(y[contiguous].sum())
            hits[h][1] += int(contiguous.sum())
    return {h: (n_hit / n if n else float("nan")) for h, (n_hit, n) in hits.items()}


def attach_event_columns(scores: pd.DataFrame) -> pd.DataFrame:
    out = scores.copy()
    if "subsequent_return" not in out.columns:
        out["subsequent_return"] = out["actual_close"] / out["origin_close"] - 1.0
    if "actual_up" not in out.columns:
        out["actual_up"] = (out["actual_close"] > out["origin_close"]).astype(int)
    return out
