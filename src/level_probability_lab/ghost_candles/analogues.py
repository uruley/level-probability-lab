from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.time_model import as_utc


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


def _window_features(ohlcv: np.ndarray) -> np.ndarray:
    """Scale-free features from lookback OHLCV (N, 5) = O,H,L,C,V. Not fitted on eval day."""
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
    return np.concatenate([path, np.array([vol, rng, v_rel], dtype=np.float64)])


def _distance(query: np.ndarray, corpus: np.ndarray, path_len: int) -> np.ndarray:
    path_d = np.linalg.norm(corpus[:, :path_len] - query[:path_len], axis=1) / np.sqrt(path_len)
    scalars_q = np.clip(query[path_len:], 1e-12, None)
    scalars_c = np.clip(corpus[:, path_len:], 1e-12, None)
    scalar_d = np.abs(np.log(scalars_c / scalars_q)).sum(axis=1)
    return path_d + 0.25 * scalar_d


class AnalogueIndex:
    """Prior completed windows whose subsequent 5 minutes are also known before origin."""

    def __init__(self, lookback: int = 120, horizon: int = 5, k: int = 50) -> None:
        self.lookback = int(lookback)
        self.horizon = int(horizon)
        self.k = int(k)
        self.features: np.ndarray | None = None
        self.paths: np.ndarray | None = None
        self.lookback_last: np.ndarray | None = None
        self.horizon_last: np.ndarray | None = None
        self.lookback_first: np.ndarray | None = None
        self.session_ids: np.ndarray | None = None
        self.last_close: np.ndarray | None = None

    def fit(self, history: pd.DataFrame) -> "AnalogueIndex":
        work = history.copy()
        work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
        work = work.sort_values("bar_start")
        feats: list[np.ndarray] = []
        paths: list[np.ndarray] = []
        lb_last: list[np.datetime64] = []
        hz_last: list[np.datetime64] = []
        lb_first: list[np.datetime64] = []
        sess: list[str] = []
        last_close: list[float] = []
        grouped = work.groupby(work["session_date"].astype(str), sort=False)
        need = self.lookback + self.horizon
        cols = ["open", "high", "low", "close", "volume"]
        for session_key, grp in grouped:
            grp = grp.sort_values("bar_start")
            if len(grp) < need:
                continue
            starts = pd.to_datetime(grp["bar_start"], utc=True).to_numpy(dtype="datetime64[ns]")
            deltas = np.diff(starts).astype("timedelta64[s]").astype(np.int64)
            if not np.all(deltas == 60):
                # allow a session with internal gaps by skipping broken windows
                ok = np.concatenate([[True], deltas == 60])
            else:
                ok = np.ones(len(grp), dtype=bool)
            ohlcv = grp[cols].to_numpy(dtype=np.float64)
            n = len(grp)
            for i in range(self.lookback - 1, n - self.horizon):
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
                feats.append(_window_features(ohlcv[sl]))
                paths.append(ohlcv[fut][:, :4])
                lb_first.append(lb_starts[0])
                lb_last.append(lb_starts[-1])
                hz_last.append(fut_starts[-1])
                sess.append(str(session_key))
                last_close.append(float(ohlcv[sl][-1, 3]))
        if not feats:
            self.features = np.zeros((0, self.lookback + 3))
            self.paths = np.zeros((0, self.horizon, 4))
            self.lookback_last = np.array([], dtype="datetime64[ns]")
            self.horizon_last = np.array([], dtype="datetime64[ns]")
            self.lookback_first = np.array([], dtype="datetime64[ns]")
            self.session_ids = np.array([], dtype=object)
            self.last_close = np.array([], dtype=np.float64)
            return self
        self.features = np.vstack(feats)
        self.paths = np.stack(paths, axis=0)
        self.lookback_last = np.array(lb_last, dtype="datetime64[ns]")
        self.horizon_last = np.array(hz_last, dtype="datetime64[ns]")
        self.lookback_first = np.array(lb_first, dtype="datetime64[ns]")
        self.session_ids = np.array(sess, dtype=object)
        self.last_close = np.asarray(last_close, dtype=np.float64)
        return self

    def query(self, window: pd.DataFrame, origin_bar_start, k: int | None = None) -> tuple[np.ndarray, dict]:
        if self.features is None or len(self.features) == 0:
            raise ValueError("AnalogueIndex.fit() produced no windows")
        k = int(k or self.k)
        origin = np.datetime64(as_utc(origin_bar_start).tz_localize(None) if as_utc(origin_bar_start).tzinfo else as_utc(origin_bar_start), "ns")
        # compare tz-aware via utc ns
        origin_ns = pd.Timestamp(as_utc(origin_bar_start)).tz_convert("UTC").tz_localize(None).to_datetime64()
        eligible = (self.horizon_last < origin_ns) & (self.lookback_last < origin_ns)
        if not np.any(eligible):
            raise ValueError(f"no prior analogue windows before {origin_bar_start}")
        ohlcv = window[["open", "high", "low", "close", "volume"]].to_numpy(dtype=np.float64)
        query = _window_features(ohlcv)
        dist = _distance(query, self.features[eligible], path_len=len(window))
        take = min(k, int(dist.shape[0]))
        idx_local = np.argpartition(dist, take - 1)[:take]
        order = idx_local[np.argsort(dist[idx_local])]
        elig_idx = np.flatnonzero(eligible)[order]
        paths = self.paths[elig_idx].copy()
        src_last = np.clip(self.last_close[elig_idx], 1e-12, None)[:, None, None]
        query_last = float(window.iloc[-1]["close"])
        paths = paths / src_last * query_last
        firsts = self.lookback_first[elig_idx]
        lasts = self.lookback_last[elig_idx]
        hz = self.horizon_last[elig_idx]
        windows = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in zip(firsts, lasts)]
        overlap = analogue_overlap_report(windows)
        meta = {
            "n": int(len(elig_idx)),
            "k_requested": k,
            "analogue_lookback_last_starts": [pd.Timestamp(x, tz="UTC").isoformat() for x in lasts],
            "analogue_horizon_last_starts": [pd.Timestamp(x, tz="UTC").isoformat() for x in hz],
            "analogue_session_ids": [str(s) for s in self.session_ids[elig_idx]],
            "n_distinct_sessions": int(len(set(self.session_ids[elig_idx].tolist()))),
            "distances": [float(d) for d in dist[order]],
            "overlap": overlap,
        }
        return paths, meta
