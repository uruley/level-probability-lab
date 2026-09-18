"""Pooled ghost-candle evaluation across local complete QQQ sessions.

Fixed benchmark (not tuned on 2026-08-14):
  lookback=120, horizon=5, sample_count=50, seed=42
  engines: persistence, historical-analogue, kronos-mini, kronos-small
  2026-08-14 is a debug slice, not protected evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from level_probability_lab.ghost_candles.adapter import make_kronos_forecaster
from level_probability_lab.ghost_candles.analogues import AnalogueIndex
from level_probability_lab.ghost_candles.chart import write_replay_html
from level_probability_lab.ghost_candles.data import (
    HISTORY_PARQUET,
    PILOT_PARQUET,
    list_complete_qqq_sessions,
    load_qqq_session,
    load_regular_qqq,
)
from level_probability_lab.ghost_candles.direction import summarize_direction
from level_probability_lab.ghost_candles.env import require_cuda_env
from level_probability_lab.ghost_candles.evaluate import score_engine
from level_probability_lab.ghost_candles.ledger import append_ledger, write_leaderboard
from level_probability_lab.ghost_candles.ohlc import representative_path, uncertainty_region
from level_probability_lab.ghost_candles.replay import run_replay
from level_probability_lab.ghost_candles.scoring import persistence_recent_range_baseline
from level_probability_lab.ghost_candles.storage import ForecastStore
from level_probability_lab.ghost_candles.windows import completed_input_window, future_session_timestamps
from level_probability_lab.paths import ensure_dir, project_root
from level_probability_lab.storage import write_json, write_parquet
from level_probability_lab.time_model import as_utc

LOOKBACK = 120
HORIZON = 5
SAMPLE_COUNT = 50
SEED = 42
DEBUG_DAY = "2026-08-14"


class PersistenceForecaster:
    model_name = "persistence"
    model_revision = "flat-close+median-lookback-range"
    tokenizer_name = ""
    tokenizer_revision = ""
    last_meta = None

    def forecast_paths(self, window, future_ts, sample_count: int, seed: int):
        last = float(window.iloc[-1]["close"])
        ranges = (window["high"] - window["low"]).astype(float).tolist()
        path = np.asarray(persistence_recent_range_baseline(last, ranges, len(future_ts)), dtype=np.float64)
        paths = np.repeat(path[None, :, :], max(int(sample_count), 1), axis=0)
        return paths, 0.0


class AnalogueForecaster:
    model_name = "historical-analogue"
    model_revision = "path+vol+range+volume euclidean k=50"
    tokenizer_name = ""
    tokenizer_revision = ""

    def __init__(self, index: AnalogueIndex) -> None:
        self.index = index
        self.last_meta = None

    def forecast_paths(self, window, future_ts, sample_count: int, seed: int):
        origin = window.iloc[-1]["bar_start"]
        paths, meta = self.index.query(window, origin, k=sample_count)
        self.last_meta = meta
        return paths, 0.0


def _store_for(root: Path, engine: str, session: str) -> tuple[Path, ForecastStore]:
    path = root / "data" / "ghost_candles" / "eval" / engine / session / "forecasts.jsonl"
    ensure_dir(path.parent)
    return path, ForecastStore(path)


def _run_or_reuse(bars, forecaster, store_path: Path, env, session: str, engine: str) -> list[dict]:
    if store_path.exists():
        existing = ForecastStore(store_path)
        rows = existing.all()
        if len(rows) >= 200:
            print(f"  reuse {engine} {session} n={len(rows)}")
            return rows
        store_path.unlink()
    store = ForecastStore(store_path)
    print(f"  run {engine} {session}")
    return run_replay(
        bars,
        forecaster,
        store,
        lookback=LOOKBACK,
        horizon=HORIZON,
        sample_count=SAMPLE_COUNT,
        seed=SEED,
        env_metadata=env,
        symbol="QQQ",
    )


def _reliability(scores: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    work = scores.dropna(subset=["p_close_gt_origin"]).copy()
    if work.empty:
        return work
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    work["p_bin"] = pd.cut(work["p_close_gt_origin"], bins=bins, include_lowest=True)
    grouped = work.groupby(["engine", "horizon_minutes", "p_bin"], observed=True)
    out = grouped.agg(
        n=("actual_up", "size"),
        predicted_p=("p_close_gt_origin", "mean"),
        actual_freq=("actual_up", "mean"),
        brier=("brier_up", "mean"),
    ).reset_index()
    out["p_bin"] = out["p_bin"].astype(str)
    out["calibration_gap"] = (out["predicted_p"] - out["actual_freq"]).abs()
    return out


def _leaderboard_rows(scores: pd.DataFrame, slice_name: str) -> list[dict]:
    vol_med = float(scores["lookback_vol"].median()) if "lookback_vol" in scores else 0.0
    tagged = scores.copy()
    tagged["vol_bucket"] = np.where(tagged["lookback_vol"] >= vol_med, "high_vol", "low_vol")
    rows = []
    for engine, eg in tagged.groupby("engine"):
        for horizon, hg in eg.groupby("horizon_minutes"):
            hits = [None if pd.isna(x) else float(x) for x in hg["directional_hit"].tolist()]
            direction = summarize_direction(hits)
            brier = hg["brier_up"].dropna()
            rows.append(
                {
                    "slice": slice_name,
                    "engine": engine,
                    "horizon_minutes": int(horizon),
                    "n": int(len(hg)),
                    "median_close_mae": float(hg["median_close_abs_error"].mean()),
                    "q10_q90_coverage": float(hg["actual_in_close_q10_q90"].mean()),
                    "brier_up": float(brier.mean()) if len(brier) else None,
                    "directional_accuracy": direction["directional_accuracy"],
                    "n_directional": direction["n_directional"],
                    "neutral_rate": direction["neutral_rate"],
                }
            )
    return rows


def _breakdown(scores: pd.DataFrame) -> list[dict]:
    vol_med = float(scores["lookback_vol"].median())
    work = scores.copy()
    work["vol_bucket"] = np.where(work["lookback_vol"] >= vol_med, "high_vol", "low_vol")
    rows = []
    for cols in (("horizon_minutes",), ("session_slot",), ("vol_bucket",), ("path_regime",), ("horizon_minutes", "session_slot")):
        for key, g in work.groupby(list(cols)):
            for engine, eg in g.groupby("engine"):
                hits = [None if pd.isna(x) else float(x) for x in eg["directional_hit"].tolist()]
                direction = summarize_direction(hits)
                brier = eg["brier_up"].dropna()
                label = key if not isinstance(key, tuple) else "|".join(str(x) for x in key)
                rows.append(
                    {
                        "group": "+".join(cols),
                        "key": str(label),
                        "engine": engine,
                        "n": int(len(eg)),
                        "median_close_mae": float(eg["median_close_abs_error"].mean()),
                        "brier_up": float(brier.mean()) if len(brier) else None,
                        "directional_accuracy": direction["directional_accuracy"],
                        "neutral_rate": direction["neutral_rate"],
                    }
                )
    return rows


def run_experiment() -> dict:
    env = require_cuda_env()
    root = project_root()
    eval_sessions = list_complete_qqq_sessions(PILOT_PARQUET)
    print(f"complete QQQ sessions in pilot: {len(eval_sessions)} -> {eval_sessions}")
    if not eval_sessions:
        raise RuntimeError("no complete local QQQ sessions")

    print("building analogue index from local history (prior windows only at query time)")
    history = load_regular_qqq(HISTORY_PARQUET if HISTORY_PARQUET.exists() else PILOT_PARQUET)
    print(f"  regular QQQ history bars: {len(history)}")
    analogue_index = AnalogueIndex(lookback=LOOKBACK, horizon=HORIZON, k=SAMPLE_COUNT).fit(history)
    print(f"  analogue windows: {0 if analogue_index.features is None else len(analogue_index.features)}")

    persist = PersistenceForecaster()
    analogue = AnalogueForecaster(analogue_index)

    print("loading Kronos-small")
    small = make_kronos_forecaster("small", device="cuda:0")
    print("loading Kronos-mini")
    mini = make_kronos_forecaster("mini", device="cuda:0")

    # Reuse the first-day small run if present.
    legacy = root / "data" / "ghost_candles" / DEBUG_DAY / "forecasts.jsonl"
    dest_small_debug = root / "data" / "ghost_candles" / "eval" / "kronos-small" / DEBUG_DAY / "forecasts.jsonl"
    if legacy.exists() and not dest_small_debug.exists():
        ensure_dir(dest_small_debug.parent)
        dest_small_debug.write_bytes(legacy.read_bytes())
        print(f"copied legacy {DEBUG_DAY} Kronos-small forecasts")

    all_scores = []
    engines_debug: dict[str, list[dict]] = {}
    debug_bars = None

    for session in eval_sessions:
        print(f"\n=== {session} ===")
        bars = load_qqq_session(PILOT_PARQUET, session)
        issued = {}
        for engine, fc in (
            ("persistence", persist),
            ("historical-analogue", analogue),
            ("kronos-mini", mini),
            ("kronos-small", small),
        ):
            path, _store = _store_for(root, engine, session)
            rows = _run_or_reuse(bars, fc, path, env, session, engine)
            for row in rows:
                row["session_date"] = session
                row["engine"] = engine
            issued[engine] = rows
            scored = score_engine(rows, bars, engine=engine)
            scored["session_date"] = session
            all_scores.append(scored)
        if session == DEBUG_DAY:
            debug_bars = bars
            engines_debug = {
                "kronos-small": issued["kronos-small"],
                "kronos-mini": issued["kronos-mini"],
                "historical-analogue": issued["historical-analogue"],
            }

    scores = pd.concat(all_scores, ignore_index=True)
    vol_med = float(scores["lookback_vol"].median())
    scores["vol_bucket"] = np.where(scores["lookback_vol"] >= vol_med, "high_vol", "low_vol")
    out_dir = root / "data" / "ghost_candles" / "experiments"
    ensure_dir(out_dir)
    write_parquet(scores, out_dir / "scores.parquet")
    reliability = _reliability(scores)
    write_parquet(reliability, out_dir / "reliability.parquet")

    pooled = _leaderboard_rows(scores, "all_complete_pilot_sessions")
    debug = _leaderboard_rows(scores.loc[scores["session_date"] == DEBUG_DAY], "debug_2026-08-14")
    holdout_days = scores.loc[scores["session_date"] != DEBUG_DAY]
    other = _leaderboard_rows(holdout_days, "pilot_excluding_debug_day") if not holdout_days.empty else []
    board = pooled + other + debug
    write_leaderboard(out_dir / "leaderboard.json", board)
    breakdown = _breakdown(scores)
    write_json({"vol_median": vol_med, "rows": breakdown}, out_dir / "breakdown.json")

    record = {
        "experiment_id": "ghost-eval-v1-pilot-complete-sessions",
        "config": {
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "sample_count": SAMPLE_COUNT,
            "seed": SEED,
            "engines": ["persistence", "historical-analogue", "kronos-mini", "kronos-small"],
            "debug_day": DEBUG_DAY,
            "eval_sessions": eval_sessions,
            "analogue_corpus": str(HISTORY_PARQUET if HISTORY_PARQUET.exists() else PILOT_PARQUET),
            "analogue_windows": int(len(analogue_index.features) if analogue_index.features is not None else 0),
        },
        "environment": env,
        "n_score_rows": int(len(scores)),
        "leaderboard_pooled": pooled,
    }
    append_ledger(out_dir / "ledger.jsonl", record)
    write_json(record, out_dir / "latest.json")

    if debug_bars is not None and engines_debug:
        html = root / "data" / "ghost_candles" / DEBUG_DAY / "replay.html"
        write_replay_html(
            html,
            bars=debug_bars,
            session_date=DEBUG_DAY,
            symbol="QQQ",
            engines=engines_debug,
            meta={"lookback": LOOKBACK, "horizon": HORIZON, "sample_count": SAMPLE_COUNT, "seed": SEED, **env},
        )
        print(f"updated replay html {html}")

    print(json.dumps({"n_sessions": len(eval_sessions), "n_score_rows": int(len(scores))}, indent=2))
    return record


def main(argv: list[str] | None = None) -> int:
    run_experiment()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
