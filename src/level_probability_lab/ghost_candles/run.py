from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from level_probability_lab.ghost_candles.adapter import KronosPathForecaster
from level_probability_lab.ghost_candles.chart import write_freeze_png, write_replay_html
from level_probability_lab.ghost_candles.data import discover_qqq_parquet, load_qqq_session
from level_probability_lab.ghost_candles.env import require_cuda_env
from level_probability_lab.ghost_candles.replay import run_replay
from level_probability_lab.ghost_candles.scoring import score_forecasts
from level_probability_lab.ghost_candles.storage import ForecastStore
from level_probability_lab.paths import ensure_dir, project_root
from level_probability_lab.storage import write_json, write_parquet


def run_ghost_replay(
    *,
    session_date: str = "2026-08-14",
    lookback: int = 120,
    horizon: int = 5,
    sample_count: int = 50,
    seed: int = 42,
    input_parquet: Path | None = None,
    out_dir: Path | None = None,
    kronos_root: Path = Path(r"C:\Users\ruley\Kronos"),
) -> dict:
    env = require_cuda_env()
    root = project_root()
    parquet = Path(input_parquet) if input_parquet else discover_qqq_parquet(root)
    if not parquet.exists():
        raise FileNotFoundError(
            f"no local QQQ parquet at {parquet}; refusing to purchase Databento data"
        )
    bars = load_qqq_session(parquet, session_date)
    dest = Path(out_dir) if out_dir else root / "data" / "ghost_candles" / session_date
    ensure_dir(dest)
    store_path = dest / "forecasts.jsonl"
    if store_path.exists():
        store_path.unlink()
    store = ForecastStore(store_path)

    print(f"loaded {len(bars)} regular-session QQQ bars from {parquet}")
    print(f"session {session_date}  lookback={lookback} horizon={horizon} samples={sample_count}")
    forecaster = KronosPathForecaster(kronos_root=kronos_root, device="cuda:0")
    # Warm-up, excluded from stored inference times.
    warm_window = bars.iloc[:lookback]
    from level_probability_lab.ghost_candles.windows import future_session_timestamps

    warm_ts = future_session_timestamps(bars, bars.iloc[lookback - 1]["bar_start"], horizon)
    _paths, warm_s = forecaster.forecast_paths(warm_window, warm_ts, sample_count=1, seed=seed)
    print(f"warmup 1-path inference {warm_s:.3f}s")

    issued = run_replay(
        bars,
        forecaster,
        store,
        lookback=lookback,
        horizon=horizon,
        sample_count=sample_count,
        seed=seed,
        env_metadata=env,
        symbol="QQQ",
    )
    scores = score_forecasts(issued, bars)
    score_path = dest / "scores.parquet"
    write_parquet(scores, score_path)
    html_path = dest / "replay.html"
    write_replay_html(
        html_path,
        bars=bars,
        forecasts=issued,
        session_date=session_date,
        symbol="QQQ",
        meta={"lookback": lookback, "horizon": horizon, "sample_count": sample_count, "seed": seed, **env},
    )
    png_path = dest / "freeze_frame.png"
    mid = issued[len(issued) // 2] if issued else None
    if mid is not None:
        write_freeze_png(png_path, bars=bars, forecast=mid)

    summary = _summarize(issued, scores, env, parquet, dest, html_path, png_path, warm_s)
    write_json(summary, dest / "summary.json")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_horizon"}, indent=2, default=str))
    print("per-horizon mean abs close error:")
    print(summary["per_horizon"])
    return summary


def _summarize(issued, scores, env, parquet, dest, html_path, png_path, warm_s) -> dict:
    n = len(issued)
    infer = [float(r["inference_time_s"]) for r in issued] if issued else [0.0]
    per = {}
    if not scores.empty:
        grouped = scores.groupby("horizon_minutes")
        per = {
            int(h): {
                "n": int(g.shape[0]),
                "kronos_close_mae": float(g["kronos_close_abs_error"].mean()),
                "baseline_close_mae": float(g["baseline_close_abs_error"].mean()),
                "kronos_open_mae": float(g["kronos_open_abs_error"].mean()),
                "baseline_open_mae": float(g["baseline_open_abs_error"].mean()),
                "kronos_high_mae": float(g["kronos_high_abs_error"].mean()),
                "baseline_high_mae": float(g["baseline_high_abs_error"].mean()),
                "kronos_low_mae": float(g["kronos_low_abs_error"].mean()),
                "baseline_low_mae": float(g["baseline_low_abs_error"].mean()),
                "kronos_range_mae": float(g["kronos_range_error"].mean()),
                "baseline_range_mae": float(g["baseline_range_error"].mean()),
                "kronos_direction_hit_rate": float(g["kronos_direction_hit"].mean()),
                "baseline_direction_hit_rate": float(g["baseline_direction_hit"].mean()),
            }
            for h, g in grouped
        }
    return {
        "n_forecasts": n,
        "n_scored_rows": int(len(scores)),
        "mean_inference_s": float(sum(infer) / len(infer)),
        "warmup_inference_s": float(warm_s),
        "source_parquet": str(parquet),
        "out_dir": str(dest),
        "html": str(html_path),
        "png": str(png_path) if png_path.exists() else None,
        "environment": env,
        "per_horizon": per,
    }


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Historical QQQ ghost-candle replay (Kronos-small).")
    p.add_argument("--session", default="2026-08-14")
    p.add_argument("--lookback", type=int, default=120)
    p.add_argument("--horizon", type=int, default=5)
    p.add_argument("--samples", type=int, default=50)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--input", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--kronos-root", default=r"C:\Users\ruley\Kronos")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)
    run_ghost_replay(
        session_date=args.session,
        lookback=args.lookback,
        horizon=args.horizon,
        sample_count=args.samples,
        seed=args.seed,
        input_parquet=Path(args.input) if args.input else None,
        out_dir=Path(args.out_dir) if args.out_dir else None,
        kronos_root=Path(args.kronos_root),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
