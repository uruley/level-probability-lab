from __future__ import annotations

from pathlib import Path

from level_probability_lab.config import Config, load_config
from level_probability_lab.context import join_context
from level_probability_lab.labeling import build_labels
from level_probability_lab.normalize import normalize_ohlcv
from level_probability_lab.paths import ensure_data_layout
from level_probability_lab.storage import write_json, write_parquet
from level_probability_lab.summary import SYNTHETIC_BANNER, label_summary
from level_probability_lab.synthetic import generate_synthetic_ohlcv
from level_probability_lab.validation import validate_normalized


def _normalize_kwargs(cfg: Config, *, is_synthetic: bool, source_dataset: str) -> dict:
    return {
        "calendar_name": cfg.get("time", "calendar", default="NYSE"),
        "interval_minutes": int(cfg.get("time", "bar_interval_minutes", default=1)),
        "publication_lag_seconds": int(cfg.get("time", "publication_lag_seconds", default=0)),
        "max_no_trade_gap_minutes": int(cfg.get("time", "max_no_trade_gap_minutes", default=5)),
        "discontinuity_log_return": float(cfg.get("time", "discontinuity_log_return", default=0.08)),
        "source_dataset": source_dataset,
        "source_schema": str(cfg.get("databento", "schema", default="ohlcv-1m")),
        "is_synthetic": is_synthetic,
    }


def run_normalize_validate_label(raw, cfg: Config, *, is_synthetic: bool, source_dataset: str, out_dir: Path):
    normalized = normalize_ohlcv(raw, **_normalize_kwargs(cfg, is_synthetic=is_synthetic, source_dataset=source_dataset))
    report = validate_normalized(normalized)
    report.raise_if_errors()
    labels = build_labels(normalized, cfg.get)
    context_symbols = cfg.get("prediction", "context_symbols", default=["NVDA"]) or []
    stale = int(cfg.get("time", "context_stale_seconds", default=60))
    for i, sym in enumerate(context_symbols):
        prefix = "context" if i == 0 else f"context_{str(sym).lower()}"
        labels = join_context(labels, normalized, str(sym), stale, prefix=prefix)
    summary = label_summary(labels, is_synthetic=is_synthetic)
    write_parquet(normalized, out_dir / "normalized.parquet")
    write_parquet(labels, out_dir / "labels.parquet")
    write_json(
        {
            "validation_ok": report.ok,
            "validation_errors": report.errors,
            "validation_warnings": report.warnings,
            "validation_stats": report.stats,
            "labels": summary,
        },
        out_dir / "summary.json",
    )
    return normalized, labels, summary, report


def run_smoke(cfg: Config | None = None, root: Path | None = None) -> dict:
    root = root or (cfg.project_root if cfg is not None else None)
    if cfg is None:
        from level_probability_lab.paths import project_root

        root = root or project_root()
        cfg = load_config(root / "configs" / "smoke.yaml", root=root)
    layout = ensure_data_layout(cfg.project_root, cfg.get("paths", "data_dir", default="data"))
    out_dir = layout["smoke"]
    raw = generate_synthetic_ohlcv(
        start=str(cfg.get("synthetic", "start", default="2024-06-28")),
        end=str(cfg.get("synthetic", "end", default="2024-07-05")),
        seed=int(cfg.get("synthetic", "seed", default=42)),
        qqq_start=float(cfg.get("synthetic", "qqq_start_price", default=450.0)),
        spy_start=float(cfg.get("synthetic", "spy_start_price", default=550.0)),
        sigma=float(cfg.get("synthetic", "sigma", default=0.0004)),
        calendar_name=str(cfg.get("time", "calendar", default="NYSE")),
    )
    write_parquet(raw, out_dir / "raw_synthetic.parquet")
    normalized, labels, summary, report = run_normalize_validate_label(
        raw,
        cfg,
        is_synthetic=True,
        source_dataset="SYNTHETIC",
        out_dir=out_dir,
    )
    return {
        "banner": SYNTHETIC_BANNER,
        "out_dir": str(out_dir),
        "n_raw": int(len(raw)),
        "n_normalized": int(len(normalized)),
        "n_labels": int(len(labels)),
        "validation_ok": report.ok,
        "summary": summary,
    }


def run_validate_and_label(cfg: Config, input_parquet: Path, out_dir: Path, *, is_synthetic: bool = False) -> dict:
    from level_probability_lab.storage import read_parquet

    raw = read_parquet(input_parquet)
    if "bar_status" in raw.columns:
        raw = raw[raw["bar_status"] == "observed"].copy()
    if "ts_event" not in raw.columns and "bar_start" in raw.columns:
        raw = raw.copy()
        raw["ts_event"] = raw["bar_start"]
    if {"open", "high", "low", "close"}.issubset(raw.columns):
        raw = raw.dropna(subset=["open", "high", "low", "close"])
    dataset = "SYNTHETIC" if is_synthetic else str(cfg.get("databento", "dataset", default="local"))
    normalized, labels, summary, report = run_normalize_validate_label(
        raw,
        cfg,
        is_synthetic=is_synthetic,
        source_dataset=dataset,
        out_dir=out_dir,
    )
    return {
        "n_normalized": int(len(normalized)),
        "n_labels": int(len(labels)),
        "validation_ok": report.ok,
        "summary": summary,
        "out_dir": str(out_dir),
    }
