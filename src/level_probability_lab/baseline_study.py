"""Frozen, offline May/June 2026 QQQ study. July outcomes remain sealed.

Run with the project Python: -m level_probability_lab.baseline_study.
Forecast files are exclusive-create per origin; scoring starts only after both
models have finished. Re-running resumes missing forecasts, without rewriting.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .calendar import session_schedule
from .lab import BASE_REVISION, ROOT, load_day

SMALL_REVISION = "901c26c1332695a2a8f243eb2f37243a37bea320"
CONFIG = dict(version=1, symbol="QQQ", development=["2026-05-01", "2026-05-31"],
              validation=["2026-06-01", "2026-06-30"], sealed_holdout=["2026-07-01", "2026-07-31"],
              lookback=120, horizon=5, stride_minutes=5, origin_offset_minutes=119,
              sample_count=25, seed=42, temperature=1.0, top_p=.9, top_k=0,
              base_revision=BASE_REVISION, small_revision=SMALL_REVISION,
              tokenizer_revision="0e0117387f39004a9016484a186a908917e22426",
              bootstrap_seed=20260919, bootstrap_replicates=2000,
              probability_event="future close > origin close (ties count as not-up)",
              direction="sign of median close minus origin; exclude predicted or actual neutral",
              source="data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet")


def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())


def eligible_origins(bars, opening, closing):
    """Require the exact input AND target minute grid; never fill a missing bar."""
    starts = pd.DatetimeIndex(bars.bar_start)
    if starts.has_duplicates:
        raise ValueError("duplicate timestamps")
    available = set(starts)
    candidates = pd.date_range(opening + pd.Timedelta(minutes=119),
                               closing - pd.Timedelta(minutes=6), freq="5min")
    return [t for t in candidates if set(pd.date_range(t-pd.Timedelta(minutes=119),
                t+pd.Timedelta(minutes=5), freq="min")).issubset(available)]


def score_paths(paths, actual, origin):
    paths, actual = np.asarray(paths, float), np.asarray(actual, float)
    median = np.median(paths, axis=0)
    lo, hi = np.quantile(paths, [.1, .9], axis=0)
    predicted_sign, actual_sign = np.sign(median-origin), np.sign(actual-origin)
    valid_direction = (predicted_sign != 0) & (actual_sign != 0)
    p_up = np.mean(paths > origin, axis=0)
    return dict(predicted=median, actual=actual, abs_error=abs(median-actual),
        squared_error=(median-actual)**2, baseline_abs_error=abs(origin-actual),
        baseline_squared_error=(origin-actual)**2, p_up=p_up, up=(actual>origin).astype(int),
        brier=(p_up-(actual>origin))**2, covered=((actual>=lo)&(actual<=hi)).astype(int),
        interval_width=hi-lo, direction_valid=valid_direction.astype(int),
        direction_correct=((predicted_sign==actual_sign)&valid_direction).astype(int))


def paired_bootstrap(frame):
    """Resample whole sessions, retaining paired forecast/baseline errors."""
    grouped = frame.assign(delta=frame.abs_error-frame.baseline_abs_error).groupby("date").delta.agg(["sum", "count"])
    rng = np.random.default_rng(CONFIG["bootstrap_seed"])
    indices = rng.integers(0, len(grouped), size=(CONFIG["bootstrap_replicates"], len(grouped)))
    samples = grouped["sum"].to_numpy()[indices].sum(axis=1)/grouped["count"].to_numpy()[indices].sum(axis=1)
    return dict(mae_difference=float(grouped["sum"].sum()/grouped["count"].sum()),
                ci95=np.quantile(samples, [.025, .975]).tolist(), sessions=len(grouped))


def prepare(output):
    source = ROOT / CONFIG["source"]
    source_stat = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as f:
        for block in iter(lambda: f.read(8*1024*1024), b""):
            digest.update(block)
    config = {**CONFIG, "source_size": source_stat.st_size, "source_mtime_ns": source_stat.st_mtime_ns,
              "source_sha256": digest.hexdigest(),
              "lab_sha256": hashlib.sha256((Path(__file__).parent/"lab.py").read_bytes()).hexdigest(),
              "kronos_python_sha256": {str(p.relative_to(Path(r"C:\Users\ruley\Kronos"))):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(Path(r"C:\Users\ruley\Kronos\model").rglob("*.py"))},
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "adapter_sha256": hashlib.sha256((Path(__file__).parent/"ghost_candles/adapter.py").read_bytes()).hexdigest()}
    manifest = output/"frozen_config.json"
    if manifest.exists():
        if json.loads(manifest.read_text()) != config:
            raise ValueError("Frozen configuration/source/code changed; use a new study output directory.")
    else:
        write_json(manifest, config, True)
    days, origins, audit = {}, [], []
    for split in ("development", "validation"):
        schedule = session_schedule(*CONFIG[split])
        for date, session in schedule.iterrows():
            date = str(date.date())
            try:
                bars = load_day(source, date)
                eligible = eligible_origins(bars, session.market_open, session.market_close)
                days[date] = bars.set_index("bar_start", drop=False)
                origins.extend(dict(date=date, split=split, origin=t.isoformat()) for t in eligible)
                audit.append(dict(date=date, split=split, rows=len(bars), eligible=len(eligible)))
            except ValueError as exc:
                audit.append(dict(date=date, split=split, eligible=0, reason=str(exc)))
    sealed = session_schedule(*CONFIG["sealed_holdout"])
    summary = dict(sessions=audit, total_origins=len(origins),
        july_calendar_sessions=len(sealed), july_data_read=False,
        july_calendar_possible_origins=sum(max(0, (int((r.market_close-r.market_open).total_seconds()/60)-125)//5+1) for r in sealed.itertuples()))
    for name, value in (("origins.json", origins), ("eligibility.json", summary)):
        path = output/name
        if path.exists():
            if json.loads(path.read_text()) != value:
                raise ValueError("Origin eligibility changed from frozen study")
        else:
            write_json(path, value, True)
    return days, origins


def forecast_file(output, model, origin):
    return output/"forecasts"/model/(pd.Timestamp(origin).strftime("%Y%m%dT%H%M%SZ")+".json")


def evaluate(output, days, origins):
    rows = []
    for model in ("base", "small"):
        for item in origins:
            record = json.loads(forecast_file(output, model, item["origin"]).read_text())
            targets = pd.to_datetime(record["targets"], utc=True)
            actual = days[item["date"]].loc[targets, "close"].to_numpy(float)
            scores = score_paths(np.asarray(record["sampled_ohlc"])[..., 3], actual, record["origin_close"])
            for h in range(5):
                rows.append({**item, "model": model, "horizon": h+1,
                    **{k: float(v[h]) for k,v in scores.items()}})
    frame = pd.DataFrame(rows)
    climatology = frame[(frame.split=="development")&(frame.model=="base")].groupby("horizon").up.mean().to_dict()
    frame["climatology_p_up"] = frame.horizon.map(climatology)
    frame["climatology_brier"] = (frame.climatology_p_up-frame.up)**2
    frame.to_csv(output/"scores.csv", index=False)
    report = dict(development_climatology=climatology, metrics=[], comparisons=[],
        limits=["May development results are descriptive; June uses May climatology.",
                "July holdout has not been read or scored.", "Nasdaq-only prints, not consolidated volume.",
                "No trading costs, profitability, or independent pretraining-overlap audit.",
                "Intervals are raw 25-path empirical quantiles, not calibrated confidence intervals.",
                "Persistence direction is neutral; directional accuracy is undefined."])
    for (split, model, horizon), group in frame.groupby(["split", "model", "horizon"]):
        n = int(group.direction_valid.sum())
        report["metrics"].append(dict(split=split, model=model, horizon=int(horizon), n=len(group),
            mae=float(group.abs_error.mean()), rmse=float(np.sqrt(group.squared_error.mean())),
            persistence_mae=float(group.baseline_abs_error.mean()), persistence_rmse=float(np.sqrt(group.baseline_squared_error.mean())),
            direction_n=n, direction_accuracy=float(group.direction_correct.sum()/n) if n else None,
            brier=float(group.brier.mean()), climatology_brier=float(group.climatology_brier.mean()),
            coverage_10_90=float(group.covered.mean()), mean_interval_width=float(group.interval_width.mean()),
            **paired_bootstrap(group)))
    for (split, model), group in frame.groupby(["split", "model"]):
        report["comparisons"].append(dict(split=split, model=model, **paired_bootstrap(group)))
    write_json(output/"report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT/"data/kronos_baseline_v1")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--max-seconds", type=float, default=7200)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    lock = output/"run.lock"
    with lock.open("x") as f:
        f.write(str(os.getpid()))
    try:
        days, origins = prepare(output)
        print(f"Frozen {len(origins)} origins; July sealed", flush=True)
        if args.prepare_only:
            return
        from .ghost_candles.adapter import KronosPathForecaster
        import torch
        start = time.monotonic()
        completed = 0
        for model in ("base", "small"):
            forecaster = None
            for item in origins:
                path = forecast_file(output, model, item["origin"])
                t = pd.Timestamp(item["origin"])
                window = days[item["date"]].loc[t-pd.Timedelta(minutes=119):t].reset_index(drop=True)
                targets = pd.date_range(t+pd.Timedelta(minutes=1), periods=5, freq="min")
                input_hash = hashlib.sha256(window[["bar_start","open","high","low","close","volume"]].to_csv(index=False).encode()).hexdigest()
                if path.exists():
                    cached = json.loads(path.read_text())
                    cached_paths = np.asarray(cached["sampled_ohlc"])
                    if (any(cached[k] != v for k,v in item.items()) or cached["model"] != model
                        or cached["targets"] != [x.isoformat() for x in targets]
                        or cached["input_sha256"] != input_hash
                        or cached["origin_close"] != float(window.iloc[-1].close)
                        or cached_paths.shape != (25,5,4) or not np.isfinite(cached_paths).all()):
                        raise ValueError(f"Invalid cached forecast {path}")
                    completed += 1
                    continue
                if time.monotonic()-start > args.max_seconds:
                    write_json(output/"progress.json", dict(status="paused_runtime_limit", completed=completed, total=2*len(origins)))
                    return
                if forecaster is None:
                    kwargs = dict(model_id="NeoQuasar/Kronos-base", model_revision=BASE_REVISION, cache_dir=ROOT/"data/models/hub") if model=="base" else {}
                    forecaster = KronosPathForecaster(**kwargs)
                paths, seconds = forecaster.forecast_paths(window, targets, 25, 42)
                if paths.shape != (25,5,4) or not np.isfinite(paths).all():
                    raise ValueError("Invalid model paths")
                write_json(path, {**item, "model": model, "origin_close":float(window.iloc[-1].close),
                    "input_sha256":input_hash,
                    "targets":[x.isoformat() for x in targets], "sampled_ohlc": paths.tolist(), "inference_seconds":seconds}, True)
                completed += 1
                if completed % 25 == 0:
                    progress = dict(status="forecasting", model=model, completed=completed, total=2*len(origins), elapsed_seconds=round(time.monotonic()-start,1))
                    write_json(output/"progress.json", progress)
                    print(json.dumps(progress), flush=True)
            del forecaster
            gc.collect()
            torch.cuda.empty_cache()
        evaluate(output, days, origins)
        write_json(output/"progress.json", dict(status="complete", completed=completed, total=2*len(origins), elapsed_seconds=round(time.monotonic()-start,1)))
        print("Study complete; report.json and scores.csv saved", flush=True)
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
