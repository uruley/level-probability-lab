"""Analogue experiment runner: session-blocked metrics, one axis at a time.

August 2026 remains development, not a reported holdout.
Kronos weights are not tuned. History purchase is not performed here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from level_probability_lab.ghost_candles.analogues import AnalogueConfig, AnalogueIndex
from level_probability_lab.ghost_candles.data import HISTORY_PARQUET, load_regular_qqq
from level_probability_lab.ghost_candles.evaluate import score_engine
from level_probability_lab.ghost_candles.experiment import AnalogueForecaster, PersistenceForecaster
from level_probability_lab.ghost_candles.kronos_calibration import apply_interval_scale, fit_interval_scale, interval_coverage
from level_probability_lab.ghost_candles.ledger import append_ledger, write_leaderboard
from level_probability_lab.ghost_candles.prob_metrics import (
    attach_event_columns,
    session_blocked_metrics,
    train_climatology,
)
from level_probability_lab.ghost_candles.windows import completed_input_window, future_session_timestamps
from level_probability_lab.exceptions import SessionBoundaryError
from level_probability_lab.paths import ensure_dir, project_root
from level_probability_lab.storage import read_parquet, write_json, write_parquet

TRAIN_LAST = "2023-12-29"
VAL_FIRST, VAL_LAST = "2024-01-02", "2024-12-31"
AUGUST_DEV = ("2026-08-03", "2026-08-31")
DEBUG_DAY = "2026-08-14"
LOOKBACKS = (15, 30, 60, 120, 240)
HORIZON = 5
DEFAULT_K = 50
DEFAULT_GROUPS = ("path", "volume", "volatility")


def _archive(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = path.with_name(f"{path.stem}_archive_{stamp}{path.suffix}")
    if not dest.exists():
        dest.write_bytes(path.read_bytes())


def _session_list(history: pd.DataFrame, first: str, last: str) -> list[str]:
    keys = pd.to_datetime(history["session_date"]).dt.strftime("%Y-%m-%d")
    return sorted({s for s in keys if first <= s <= last})


def _summarize_engine(scores: pd.DataFrame, engine: str, p_clim_by_h: dict[int, float], slice_name: str) -> list[dict[str, Any]]:
    work = attach_event_columns(scores.loc[scores["engine"] == engine])
    rows = []
    for horizon, hg in work.groupby("horizon_minutes"):
        h = int(horizon)
        p_clim = float(p_clim_by_h.get(h, np.nan))
        block = session_blocked_metrics(hg, p_clim=p_clim)
        rows.append(
            {
                "slice": slice_name,
                "engine": engine,
                "horizon_minutes": h,
                "n": block.get("n"),
                "n_sessions": block.get("n_sessions"),
                "climatology_p": p_clim,
                "brier": block.get("brier"),
                "log_loss": block.get("log_loss"),
                "bss_vs_climatology": block.get("bss_vs_climatology"),
                "brier_session_mean": block.get("brier_session_mean"),
                "brier_session_se": block.get("brier_session_se"),
                "brier_session_bootstrap_95": block.get("brier_session_bootstrap_95"),
                "log_loss_session_bootstrap_95": block.get("log_loss_session_bootstrap_95"),
                "bss_session_bootstrap_95": block.get("bss_session_bootstrap_95"),
                "calibration": block.get("calibration"),
                "reliability": block.get("reliability"),
                "median_close_mae": float(hg["median_close_abs_error"].mean()) if "median_close_abs_error" in hg else None,
                "q10_q90_coverage": float(hg["actual_in_close_q10_q90"].mean()) if "actual_in_close_q10_q90" in hg else None,
                "independence_note": block.get("independence_note"),
            }
        )
    return rows


def _climatology_engine_rows(scores: pd.DataFrame, p_clim_by_h: dict[int, float], slice_name: str) -> list[dict[str, Any]]:
    """Score a constant train climatology on the same events as `scores`."""
    if scores.empty:
        return []
    engine0 = str(scores["engine"].iloc[0])
    base = attach_event_columns(scores.loc[scores["engine"] == engine0].copy())
    fake = base.copy()
    fake["engine"] = "climatology"
    fake["p_close_gt_origin"] = fake["horizon_minutes"].map(lambda h: p_clim_by_h.get(int(h), np.nan))
    fake["median_close"] = fake["origin_close"]
    fake["median_close_abs_error"] = (fake["actual_close"] - fake["origin_close"]).abs()
    fake["actual_in_close_q10_q90"] = np.nan
    return _summarize_engine(fake, "climatology", p_clim_by_h, slice_name)


def run_existing_prob_eval(*, root: Path | None = None) -> dict[str, Any]:
    """Re-score the August ghost-eval parquet with the strengthened evaluator."""
    base = root or project_root()
    out_dir = base / "data" / "ghost_candles" / "experiments"
    scores_path = out_dir / "scores.parquet"
    if not scores_path.exists():
        raise FileNotFoundError(f"missing {scores_path}; run ghost-eval first")
    scores = attach_event_columns(read_parquet(scores_path))
    history = load_regular_qqq(HISTORY_PARQUET)
    clim = train_climatology(history, horizon=HORIZON, last_session=TRAIN_LAST)

    _archive(out_dir / "leaderboard.json")
    slices = {
        "all_complete_pilot_sessions": scores,
        "pilot_excluding_debug_day": scores.loc[scores["session_date"].astype(str) != DEBUG_DAY],
        "debug_2026-08-14": scores.loc[scores["session_date"].astype(str) == DEBUG_DAY],
    }
    board: list[dict[str, Any]] = []
    for slice_name, frame in slices.items():
        if frame.empty:
            continue
        for engine in sorted(frame["engine"].dropna().unique()):
            board.extend(_summarize_engine(frame, str(engine), clim, slice_name))
        board.extend(_climatology_engine_rows(frame, clim, slice_name))

    # Kronos-small interval calibration: first August sessions = fit, last = chrono check.
    ks = scores.loc[scores["engine"] == "kronos-small"].copy()
    ks["session_date"] = ks["session_date"].astype(str)
    sessions = sorted(ks["session_date"].unique())
    split = max(1, int(round(0.66 * len(sessions))))
    cal_days, eval_days = sessions[:split], sessions[split:]
    cal = ks.loc[ks["session_date"].isin(cal_days)]
    ev = ks.loc[ks["session_date"].isin(eval_days)]
    scale = fit_interval_scale(cal, target_coverage=0.80)
    cal_s = apply_interval_scale(cal, scale)
    ev_s = apply_interval_scale(ev, scale)
    kronos_cal = {
        "method": "median-centered q10-q90 width scale",
        "target_coverage": 0.80,
        "scale": scale,
        "fit_sessions": cal_days,
        "eval_sessions": eval_days,
        "note": "Chronological split inside August development. Not protected holdout. Kronos weights unchanged.",
        "fit_raw_coverage": float(cal["actual_in_close_q10_q90"].mean()) if not cal.empty else None,
        "fit_calibrated_coverage": interval_coverage(
            cal_s["actual_close"].to_numpy(),
            cal_s["close_q10_calibrated"].to_numpy(),
            cal_s["close_q90_calibrated"].to_numpy(),
        ) if not cal_s.empty else None,
        "eval_raw_coverage": float(ev["actual_in_close_q10_q90"].mean()) if not ev.empty else None,
        "eval_calibrated_coverage": interval_coverage(
            ev_s["actual_close"].to_numpy(),
            ev_s["close_q10_calibrated"].to_numpy(),
            ev_s["close_q90_calibrated"].to_numpy(),
        ) if not ev_s.empty else None,
    }
    write_json(kronos_cal, out_dir / "kronos_interval_calibration.json")

    write_leaderboard(out_dir / "leaderboard.json", board)
    write_json({"climatology_train_through": TRAIN_LAST, "p_close_gt_origin": clim}, out_dir / "climatology.json")

    record = {
        "experiment_id": "ghost-prob-eval-v2",
        "config": {
            "source_scores": str(scores_path),
            "climatology": "train RTH QQQ through " + TRAIN_LAST,
            "engines": sorted({*scores["engine"].astype(str).unique(), "climatology"}),
            "kronos_interval_calibration": kronos_cal,
            "august_is_development": True,
        },
        "n_score_rows": int(len(scores)),
        "leaderboard_pooled_h5": [r for r in board if r.get("horizon_minutes") == 5 and r.get("slice") == "all_complete_pilot_sessions"],
    }
    append_ledger(out_dir / "ledger.jsonl", record)
    write_json(record, out_dir / "latest_prob.json")
    return record


def _session_bars(history: pd.DataFrame, session: str) -> pd.DataFrame:
    keys = pd.to_datetime(history["session_date"]).dt.strftime("%Y-%m-%d")
    return history.loc[keys == session].sort_values("bar_start").reset_index(drop=True)


def _forecast_session(
    bars: pd.DataFrame,
    forecaster,
    *,
    lookback: int,
    horizon: int,
    stride: int,
    k: int,
    engine: str,
    session: str,
) -> list[dict]:
    issued: list[dict] = []
    n = len(bars)
    for i in range(lookback - 1, n - horizon, stride):
        last = bars.iloc[i]
        try:
            window = completed_input_window(bars.iloc[: i + 1], last["bar_start"], lookback)
            future_ts = future_session_timestamps(bars, last["bar_start"], horizon)
        except SessionBoundaryError:
            continue
        paths, inf = forecaster.forecast_paths(window, future_ts, sample_count=k, seed=42)
        extra = getattr(forecaster, "last_meta", None)
        issued.append(
            {
                "forecast_id": f"{engine}|{session}|{last['bar_start']}",
                "session_date": session,
                "last_input_timestamp": pd.Timestamp(last["bar_start"]).isoformat(),
                "target_timestamps": [pd.Timestamp(ts).isoformat() for ts in future_ts],
                "sampled_paths": np.asarray(paths, dtype=np.float64)[:, :, :4],
                "displayed_path": np.asarray(paths, dtype=np.float64)[0, :, :4].tolist(),
                "input_window": [
                    {
                        "bar_start": str(rec.bar_start),
                        "open": float(rec.open),
                        "high": float(rec.high),
                        "low": float(rec.low),
                        "close": float(rec.close),
                        "volume": float(rec.volume),
                    }
                    for rec in window.itertuples(index=False)
                ],
                "inference_time_s": float(inf),
                "analogue_meta": extra,
                "engine": engine,
            }
        )
    return issued


def run_lookback_sweep(
    *,
    root: Path | None = None,
    max_eval_sessions: int = 40,
    origin_stride: int = 15,
    corpus_stride: int = 5,
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    """Dimension A only. History is local; no Databento call."""
    base = root or project_root()
    out_dir = ensure_dir(base / "data" / "ghost_candles" / "experiments" / "analogue_lookback")
    history = load_regular_qqq(HISTORY_PARQUET)
    clim = train_climatology(history, horizon=HORIZON, last_session=TRAIN_LAST)
    eval_sessions = _session_list(history, VAL_FIRST, VAL_LAST)[: max(1, int(max_eval_sessions))]
    persist = PersistenceForecaster()
    all_scores: list[pd.DataFrame] = []
    configs_run: list[dict[str, Any]] = []

    for lookback in LOOKBACKS:
        cfg = AnalogueConfig(
            lookback=lookback,
            horizon=HORIZON,
            k=k,
            weighting="uniform",
            feature_groups=DEFAULT_GROUPS,
            corpus_stride=corpus_stride,
        )
        print(f"fitting analogue index lookback={lookback} stride={corpus_stride}")
        index = AnalogueIndex(config=cfg).fit(history)
        analogue = AnalogueForecaster(index)
        analogue.model_revision = f"groups={'+'.join(DEFAULT_GROUPS)} k={k} lookback={lookback} uniform"
        session_scores = []
        for session in eval_sessions:
            bars = _session_bars(history, session)
            if len(bars) < lookback + HORIZON + 1:
                continue
            for engine, fc in (("persistence", persist), ("historical-analogue", analogue)):
                rows = _forecast_session(
                    bars, fc, lookback=lookback, horizon=HORIZON, stride=origin_stride, k=k, engine=engine, session=session
                )
                if not rows:
                    continue
                scored = score_engine(rows, bars, engine=engine)
                scored["lookback"] = lookback
                scored["config_id"] = f"lookback-{lookback}"
                session_scores.append(scored)
        if not session_scores:
            continue
        packed = pd.concat(session_scores, ignore_index=True)
        all_scores.append(packed)
        board = []
        for engine in packed["engine"].unique():
            board.extend(_summarize_engine(packed, str(engine), clim, f"val2024_first_{len(eval_sessions)}_lookback_{lookback}"))
        board.extend(_climatology_engine_rows(packed, clim, f"val2024_first_{len(eval_sessions)}_lookback_{lookback}"))
        write_json({"lookback": lookback, "rows": board}, out_dir / f"lookback_{lookback}.json")
        append_ledger(
            out_dir / "ledger.jsonl",
            {
                "experiment_id": f"analogue-lookback-{lookback}",
                "dimension": "lookback",
                "config": cfg.__dict__,
                "eval_sessions": eval_sessions,
                "origin_stride": origin_stride,
                "leaderboard": board,
            },
        )
        configs_run.append({"lookback": lookback, "n_score_rows": int(len(packed))})
        print(f"  lookback {lookback} rows={len(packed)}")

    scores = pd.concat(all_scores, ignore_index=True) if all_scores else pd.DataFrame()
    if not scores.empty:
        write_parquet(scores, out_dir / "scores.parquet")
    summary = {
        "experiment_id": "analogue-dimension-A-lookback",
        "budget": {"max_new_configs": len(LOOKBACKS), "dimension": "lookback", "next_frozen_until_this_lands": ["k", "weighting", "feature_groups"]},
        "eval": {"partition": "validation_2024", "sessions": eval_sessions, "origin_stride": origin_stride, "corpus_stride": corpus_stride},
        "climatology": clim,
        "configs_run": configs_run,
        "note": "August 2026 not used for these scores. Kronos not retuned. No Databento purchase.",
    }
    write_json(summary, out_dir / "summary.json")
    append_ledger(base / "data" / "ghost_candles" / "experiments" / "ledger.jsonl", summary)
    return summary
