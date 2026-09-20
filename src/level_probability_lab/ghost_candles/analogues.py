"""Historical analogues with leakage assertions and feature-group distances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from level_probability_lab.exceptions import AnalogueLeakageError
from level_probability_lab.time_model import as_utc

KNOWN_GROUPS = (
    "path",
    "volume",
    "volatility",
    "tod",
    "prev_session",
    "vwap",
    "ma",
    "bollinger",
)
KNOWN_WEIGHTING = ("uniform", "inverse-distance", "gaussian")
ONE_MIN = np.timedelta64(1, "m")


def _minute(ts) -> int:
    return int(as_utc(ts).timestamp() // 60)


def analogue_overlap_report(windows: list[tuple]) -> dict:
    """Inclusive-minute overlap among analogue lookback windows."""
    n = len(windows)
    pairs = 0
    overlapping = 0
    fracs: list[float] = []
    for i in range(n):
        a0, a1 = _minute(windows[i][0]), _minute(windows[i][1])
        len_a = a1 - a0 + 1
        for j in range(i + 1, n):
            b0, b1 = _minute(windows[j][0]), _minute(windows[j][1])
            pairs += 1
            inter = max(0, min(a1, b1) - max(a0, b0) + 1)
            if inter > 0 and len_a > 0:
                overlapping += 1
                fracs.append(inter / len_a)
    return {
        "n_windows": n,
        "n_pairs": pairs,
        "n_overlapping_pairs": overlapping,
        "mean_overlap_fraction": float(np.mean(fracs)) if fracs else 0.0,
        "max_overlap_fraction": float(np.max(fracs)) if fracs else 0.0,
    }


def neighbor_weights(distances: np.ndarray, method: str) -> np.ndarray:
    method = method.lower()
    d = np.asarray(distances, dtype=np.float64)
    if method == "uniform":
        w = np.ones_like(d)
    elif method == "inverse-distance":
        w = 1.0 / (d + 1e-12)
    elif method == "gaussian":
        sigma = float(np.median(d)) if d.size else 1.0
        sigma = max(sigma, 1e-12)
        w = np.exp(-0.5 * (d / sigma) ** 2)
    else:
        raise ValueError(f"unknown weighting {method}; expected {KNOWN_WEIGHTING}")
    total = float(w.sum())
    if total <= 0:
        return np.full_like(d, 1.0 / max(len(d), 1))
    return w / total


def _session_key_series(values) -> pd.Series:
    ts = pd.to_datetime(values)
    tz = getattr(ts.dt, "tz", None)
    if tz is not None:
        ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    return ts.dt.strftime("%Y-%m-%d")


def _as_naive_ns(value) -> np.datetime64:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_datetime64()


def _origin_ns(origin_bar_start) -> np.datetime64:
    return _as_naive_ns(as_utc(origin_bar_start))


def assert_analogues_known_before_origin(future_ends: Sequence, origin_bar_start) -> None:
    origin = _origin_ns(origin_bar_start)
    for end in future_ends:
        if not (_as_naive_ns(end) < origin):
            raise AnalogueLeakageError(
                f"analogue_future_end {pd.Timestamp(end)} is not strictly before origin {origin_bar_start}"
            )


def build_daily_table(history: pd.DataFrame) -> pd.DataFrame:
    """One row per session. Rolling stats use only completed prior sessions."""
    work = history.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    work["session_date"] = _session_key_series(work["session_date"])
    rows = []
    for sess, grp in work.groupby("session_date", sort=True):
        grp = grp.sort_values("bar_start")
        closes = grp["close"].to_numpy(dtype=np.float64)
        highs = grp["high"].to_numpy(dtype=np.float64)
        lows = grp["low"].to_numpy(dtype=np.float64)
        vols = grp["volume"].to_numpy(dtype=np.float64)
        vwap = float(np.sum(closes * vols) / (np.sum(vols) + 1e-12))
        rows.append(
            {
                "session_date": sess,
                "open": float(grp["open"].iloc[0]),
                "high": float(highs.max()),
                "low": float(lows.min()),
                "close": float(closes[-1]),
                "vwap": vwap,
            }
        )
    daily = pd.DataFrame(rows)
    if daily.empty:
        return daily
    prior_close = daily["close"].shift(1)
    daily["prev_high"] = daily["high"].shift(1)
    daily["prev_low"] = daily["low"].shift(1)
    daily["prev_close"] = prior_close
    daily["prev_vwap"] = daily["vwap"].shift(1)
    daily["ma20"] = prior_close.rolling(20, min_periods=20).mean()
    daily["ma50"] = prior_close.rolling(50, min_periods=50).mean()
    daily["ma200"] = prior_close.rolling(200, min_periods=200).mean()
    daily["ma20_slope"] = (daily["ma20"] - daily["ma20"].shift(5)) / (5.0 * daily["ma20"].replace(0, np.nan))
    daily["ma50_slope"] = (daily["ma50"] - daily["ma50"].shift(5)) / (5.0 * daily["ma50"].replace(0, np.nan))
    daily["bb_mid"] = daily["ma20"]
    daily["bb_std"] = prior_close.rolling(20, min_periods=20).std(ddof=1)
    return daily.set_index("session_date")


def _path_volume_vol(ohlcv: np.ndarray) -> dict[str, np.ndarray]:
    closes = ohlcv[:, 3]
    highs = ohlcv[:, 1]
    lows = ohlcv[:, 2]
    vols = ohlcv[:, 4]
    last = max(float(closes[-1]), 1e-12)
    path = closes / last - 1.0
    logc = np.log(np.clip(closes, 1e-12, None))
    rets = np.diff(logc)
    vol = float(np.std(rets)) if len(rets) else 0.0
    rng = float((highs.max() - lows.min()) / last)
    v_rel = float(vols[-min(20, len(vols)) :].mean() / (vols.mean() + 1e-12))
    return {"path": path, "volume": np.array([v_rel]), "volatility": np.array([vol, rng])}


def _tod_feature(last_start) -> np.ndarray:
    ny = as_utc(last_start).tz_convert("America/New_York")
    minutes = ny.hour * 60 + ny.minute - (9 * 60 + 30)
    return np.array([minutes / 390.0], dtype=np.float64)


def _daily_features(last_close: float, daily_row: pd.Series | None, groups: Sequence[str]) -> np.ndarray:
    parts: list[np.ndarray] = []
    ref = max(abs(float(last_close)), 1e-12)
    if daily_row is None:
        missing = []
        if "prev_session" in groups:
            missing.append(np.full(3, np.nan))
        if "vwap" in groups:
            missing.append(np.full(2, np.nan))
        if "ma" in groups:
            missing.append(np.full(5, np.nan))
        if "bollinger" in groups:
            missing.append(np.full(2, np.nan))
        return np.concatenate(missing) if missing else np.zeros(0)
    if "prev_session" in groups:
        pc = float(daily_row.get("prev_close", np.nan) or np.nan)
        scale = max(abs(pc), 1e-12) if np.isfinite(pc) else ref
        parts.append(
            np.array(
                [
                    (last_close - float(daily_row.get("prev_high", np.nan))) / scale,
                    (last_close - float(daily_row.get("prev_low", np.nan))) / scale,
                    (last_close - pc) / scale,
                ],
                dtype=np.float64,
            )
        )
    if "vwap" in groups:
        pc = float(daily_row.get("prev_close", np.nan) or np.nan)
        scale = max(abs(pc), 1e-12) if np.isfinite(pc) else ref
        parts.append(
            np.array(
                [
                    (last_close - float(daily_row.get("prev_vwap", np.nan))) / scale,
                    (last_close - float(daily_row.get("vwap", np.nan))) / scale,
                ],
                dtype=np.float64,
            )
        )
    if "ma" in groups:
        def _dist(ma):
            val = float(daily_row.get(ma, np.nan) or np.nan)
            if not np.isfinite(val) or val == 0:
                return np.nan
            return (last_close - val) / abs(val)
        parts.append(
            np.array(
                [
                    _dist("ma20"),
                    _dist("ma50"),
                    _dist("ma200"),
                    float(daily_row.get("ma20_slope", np.nan) or np.nan),
                    float(daily_row.get("ma50_slope", np.nan) or np.nan),
                ],
                dtype=np.float64,
            )
        )
    if "bollinger" in groups:
        mid = float(daily_row.get("bb_mid", np.nan) or np.nan)
        std = float(daily_row.get("bb_std", np.nan) or np.nan)
        width = (4.0 * std / abs(mid)) if np.isfinite(mid) and mid and np.isfinite(std) else np.nan
        pos = ((last_close - mid) / (2.0 * std)) if np.isfinite(mid) and np.isfinite(std) and std else np.nan
        parts.append(np.array([pos, width], dtype=np.float64))
    return np.concatenate(parts) if parts else np.zeros(0)


def _assemble_features(
    ohlcv: np.ndarray,
    last_start,
    daily_row: pd.Series | None,
    groups: Sequence[str],
    current_session_ohlcv: np.ndarray | None = None,
) -> np.ndarray:
    unknown = [g for g in groups if g not in KNOWN_GROUPS]
    if unknown:
        raise ValueError(f"unknown feature groups {unknown}")
    base = _path_volume_vol(ohlcv)
    parts: list[np.ndarray] = []
    if "path" in groups:
        parts.append(base["path"])
    if "volume" in groups:
        parts.append(base["volume"])
    if "volatility" in groups:
        parts.append(base["volatility"])
    if "tod" in groups:
        parts.append(_tod_feature(last_start))
    extras = _daily_features(float(ohlcv[-1, 3]), daily_row, groups)
    if extras.size:
        if "vwap" in groups and current_session_ohlcv is not None and len(current_session_ohlcv):
            # overwrite current-session VWAP distance using only completed bars today
            c = current_session_ohlcv[:, 3]
            v = current_session_ohlcv[:, 4]
            vwap_now = float(np.sum(c * v) / (np.sum(v) + 1e-12))
            last = float(ohlcv[-1, 3])
            # extras layout: prev_session(3)? then vwap(2)=[prev, current]
            offset = 3 if "prev_session" in groups else 0
            extras = extras.copy()
            extras[offset + 1] = (last - vwap_now) / max(abs(last), 1e-12)
        parts.append(extras)
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float64)


def _distance(query: np.ndarray, corpus: np.ndarray, path_len: int) -> np.ndarray:
    if corpus.size == 0:
        return np.zeros(0)
    if path_len > 0:
        path_d = np.linalg.norm(corpus[:, :path_len] - query[:path_len], axis=1) / np.sqrt(path_len)
    else:
        path_d = np.zeros(len(corpus))
    extra_q = query[path_len:]
    extra_c = corpus[:, path_len:]
    if extra_q.size == 0:
        return path_d
    # nan-safe: missing daily features -> large distance on that component
    q = np.nan_to_num(extra_q, nan=0.0)
    c = np.nan_to_num(extra_c, nan=0.0)
    miss = ~np.isfinite(extra_c) | ~np.isfinite(extra_q)
    extra_d = np.sqrt(np.mean((c - q) ** 2, axis=1) + 0.25 * miss.mean(axis=1))
    return path_d + 0.25 * extra_d


@dataclass(frozen=True)
class AnalogueConfig:
    lookback: int = 120
    horizon: int = 5
    k: int = 50
    weighting: str = "uniform"
    feature_groups: tuple[str, ...] = ("path", "volume", "volatility")
    corpus_stride: int = 1

    def __post_init__(self) -> None:
        if self.weighting not in KNOWN_WEIGHTING:
            raise ValueError(f"weighting must be one of {KNOWN_WEIGHTING}")
        unknown = [g for g in self.feature_groups if g not in KNOWN_GROUPS]
        if unknown:
            raise ValueError(f"unknown feature groups {unknown}")
        if self.corpus_stride < 1:
            raise ValueError("corpus_stride must be >= 1")


class AnalogueIndex:
    """Prior completed windows whose subsequent horizon is fully known before origin."""

    def __init__(
        self,
        lookback: int = 120,
        horizon: int = 5,
        k: int = 50,
        weighting: str = "uniform",
        feature_groups: Iterable[str] | None = None,
        corpus_stride: int = 1,
        config: AnalogueConfig | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            groups = tuple(feature_groups) if feature_groups is not None else ("path", "volume", "volatility")
            self.config = AnalogueConfig(
                lookback=int(lookback),
                horizon=int(horizon),
                k=int(k),
                weighting=str(weighting),
                feature_groups=groups,
                corpus_stride=int(corpus_stride),
            )
        self.lookback = self.config.lookback
        self.horizon = self.config.horizon
        self.k = self.config.k
        self.features: np.ndarray | None = None
        self.paths: np.ndarray | None = None
        self.lookback_last: np.ndarray | None = None
        self.lookback_first: np.ndarray | None = None
        self.horizon_first: np.ndarray | None = None
        self.horizon_last: np.ndarray | None = None
        self.future_end: np.ndarray | None = None
        self.session_ids: np.ndarray | None = None
        self.last_close: np.ndarray | None = None
        self.path_len: int = self.lookback if "path" in self.config.feature_groups else 0
        self.daily: pd.DataFrame | None = None

    def fit(self, history: pd.DataFrame) -> "AnalogueIndex":
        work = history.copy()
        work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
        work["session_date"] = _session_key_series(work["session_date"])
        work = work.sort_values(["session_date", "bar_start"])
        daily = build_daily_table(work)
        self.daily = daily
        groups = self.config.feature_groups
        feats: list[np.ndarray] = []
        paths: list[np.ndarray] = []
        lb_last: list[np.datetime64] = []
        hz_last: list[np.datetime64] = []
        hz_first: list[np.datetime64] = []
        lb_first: list[np.datetime64] = []
        fut_end: list[np.datetime64] = []
        sess: list[str] = []
        last_close: list[float] = []
        cols = ["open", "high", "low", "close", "volume"]
        need = self.lookback + self.horizon
        for session_key, grp in work.groupby("session_date", sort=False):
            grp = grp.sort_values("bar_start")
            if len(grp) < need:
                continue
            daily_row = daily.loc[session_key] if session_key in daily.index else None
            starts = pd.to_datetime(grp["bar_start"], utc=True).to_numpy(dtype="datetime64[ns]")
            deltas = np.diff(starts).astype("timedelta64[s]").astype(np.int64)
            ok = np.concatenate([[True], deltas == 60])
            ohlcv = grp[cols].to_numpy(dtype=np.float64)
            n = len(grp)
            stride = self.config.corpus_stride
            for i in range(self.lookback - 1, n - self.horizon):
                if ((i - (self.lookback - 1)) % stride) != 0:
                    continue
                sl = slice(i + 1 - self.lookback, i + 1)
                fut = slice(i + 1, i + 1 + self.horizon)
                if not ok[sl].all() or not ok[fut].all():
                    continue
                lb_starts = starts[sl]
                fut_starts = starts[fut]
                if len(lb_starts) > 1 and not np.all(np.diff(lb_starts).astype("timedelta64[s]").astype(np.int64) == 60):
                    continue
                if len(fut_starts) > 1 and not np.all(np.diff(fut_starts).astype("timedelta64[s]").astype(np.int64) == 60):
                    continue
                last_start = pd.Timestamp(lb_starts[-1], tz="UTC")
                vec = _assemble_features(
                    ohlcv[sl],
                    last_start,
                    daily_row,
                    groups,
                    current_session_ohlcv=ohlcv[: i + 1],
                )
                if vec.size == 0 or not np.isfinite(vec[: max(self.path_len, 1)]).all():
                    continue
                feats.append(vec)
                paths.append(ohlcv[fut][:, :4])
                lb_first.append(lb_starts[0])
                lb_last.append(lb_starts[-1])
                hz_first.append(fut_starts[0])
                hz_last.append(fut_starts[-1])
                fut_end.append(fut_starts[-1] + ONE_MIN)
                sess.append(str(session_key))
                last_close.append(float(ohlcv[sl][-1, 3]))
        if not feats:
            self.features = np.zeros((0, 1))
            self.paths = np.zeros((0, self.horizon, 4))
            empty = np.array([], dtype="datetime64[ns]")
            self.lookback_last = empty
            self.horizon_last = empty
            self.horizon_first = empty
            self.lookback_first = empty
            self.future_end = empty
            self.session_ids = np.array([], dtype=object)
            self.last_close = np.array([], dtype=np.float64)
            return self
        features = np.vstack(feats)
        order = np.argsort(np.array(fut_end, dtype="datetime64[ns]"))
        self.features = features[order]
        self.paths = np.stack(paths, axis=0)[order]
        self.lookback_last = np.array(lb_last, dtype="datetime64[ns]")[order]
        self.horizon_last = np.array(hz_last, dtype="datetime64[ns]")[order]
        self.horizon_first = np.array(hz_first, dtype="datetime64[ns]")[order]
        self.lookback_first = np.array(lb_first, dtype="datetime64[ns]")[order]
        self.future_end = np.array(fut_end, dtype="datetime64[ns]")[order]
        self.session_ids = np.array(sess, dtype=object)[order]
        self.last_close = np.asarray(last_close, dtype=np.float64)[order]
        if "path" in groups:
            self.path_len = self.lookback
        else:
            self.path_len = 0
        return self

    def query(self, window: pd.DataFrame, origin_bar_start, k: int | None = None) -> tuple[np.ndarray, dict]:
        if self.features is None or len(self.features) == 0:
            raise ValueError("AnalogueIndex.fit() produced no windows")
        k = int(k or self.k)
        origin_ns = _origin_ns(origin_bar_start)
        cut = int(np.searchsorted(self.future_end, origin_ns, side="left"))
        if cut <= 0:
            raise ValueError(f"no prior analogue windows with future_end < {origin_bar_start}")
        ohlcv = window[["open", "high", "low", "close", "volume"]].to_numpy(dtype=np.float64)
        daily_row = None
        if self.daily is not None and "session_date" in window.columns:
            sess = str(_session_key_series(pd.Series([window.iloc[-1]["session_date"]])).iloc[0])
            if sess in self.daily.index:
                daily_row = self.daily.loc[sess]
        query = _assemble_features(
            ohlcv,
            window.iloc[-1]["bar_start"],
            daily_row,
            self.config.feature_groups,
            current_session_ohlcv=ohlcv,
        )
        dist = _distance(query, self.features[:cut], path_len=self.path_len)
        take = min(k, int(dist.shape[0]))
        idx_local = np.argpartition(dist, take - 1)[:take]
        order = idx_local[np.argsort(dist[idx_local])]
        future_ends = self.future_end[:cut][order]
        assert_analogues_known_before_origin(future_ends, origin_bar_start)
        if np.any(future_ends >= origin_ns):
            raise AnalogueLeakageError("retrieved analogue outcome was not fully known before origin")
        paths = self.paths[:cut][order].copy()
        src_last = np.clip(self.last_close[:cut][order], 1e-12, None)[:, None, None]
        query_last = float(window.iloc[-1]["close"])
        paths = paths / src_last * query_last
        firsts = self.lookback_first[:cut][order]
        lasts = self.lookback_last[:cut][order]
        hz0 = self.horizon_first[:cut][order]
        hz1 = self.horizon_last[:cut][order]
        weights = neighbor_weights(dist[order], self.config.weighting)
        windows = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in zip(firsts, lasts)]
        overlap = analogue_overlap_report(windows)
        p_up = []
        for h in range(paths.shape[1]):
            up = (paths[:, h, 3] > query_last).astype(np.float64)
            p_up.append(float(np.sum(weights * up)))
        iso = lambda xs: [pd.Timestamp(x, tz="UTC").isoformat() for x in xs]
        meta = {
            "n": int(len(order)),
            "k_requested": k,
            "weighting": self.config.weighting,
            "feature_groups": list(self.config.feature_groups),
            "analogue_lookback_first_starts": iso(firsts),
            "analogue_lookback_last_starts": iso(lasts),
            "analogue_horizon_first_starts": iso(hz0),
            "analogue_horizon_last_starts": iso(hz1),
            "analogue_future_ends": iso(future_ends),
            "analogue_session_ids": [str(s) for s in self.session_ids[:cut][order]],
            "n_distinct_sessions": int(len(set(self.session_ids[:cut][order].tolist()))),
            "distances": [float(d) for d in dist[order]],
            "weights": [float(w) for w in weights],
            "weighted_p_close_gt_origin": p_up,
            "overlap": overlap,
        }
        return paths, meta
