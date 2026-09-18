from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from level_probability_lab.config import Config, databento_request_from_config, load_config
from level_probability_lab.exceptions import LabError
from level_probability_lab.paths import ensure_data_layout, project_root
from level_probability_lab.pipeline import run_smoke, run_validate_and_label
from level_probability_lab.providers.databento_adapter import DatabentoAdapter, request_fingerprint
from level_probability_lab.storage import read_json, read_parquet


def _cfg(args: argparse.Namespace) -> Config:
    root = Path(args.project_root) if getattr(args, "project_root", None) else project_root()
    config_path = getattr(args, "config", None)
    return load_config(config_path, root=root)


def _print_json(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def cmd_smoke(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    result = run_smoke(cfg)
    print(result["banner"])
    _print_json({k: v for k, v in result.items() if k != "banner"})
    return 0


def cmd_quote(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    request = databento_request_from_config(cfg)
    adapter = DatabentoAdapter(root=cfg.project_root)
    payload = adapter.quote(request)
    print("QUOTE ONLY — no market data downloaded, timeseries.get_range not called.")
    print(f"fingerprint: {payload['fingerprint']}")
    print(f"dataset:     {request['dataset']}")
    print(f"schema:      {request['schema']}")
    print(f"symbols:     {', '.join(request['symbols'])}")
    print(f"start:       {request['start']}")
    print(f"end:         {request['end']}  (exclusive)")
    print(f"est. cost:   {payload.get('estimated_cost_usd')}")
    print(f"records:     {payload.get('record_count')}")
    print(f"billable B:  {payload.get('billable_size_bytes')}")
    notes = payload.get("dataset_notes") or {}
    print(f"feed type:   {notes.get('feed_type')}")
    print(f"volume:      {notes.get('volume')}")
    print(f"saved:       {payload.get('quote_path')}")
    print("This is not authorization to download. Default spending cap remains $0.")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    if args.quote_manifest:
        quote = read_json(Path(args.quote_manifest))
        request = quote["request"]
        expected_fp = quote.get("fingerprint")
    else:
        request = databento_request_from_config(cfg)
        expected_fp = args.expected_fingerprint
    enabled = bool(cfg.get("databento", "download_enabled", default=False)) or bool(args.enable_download)
    cap = args.spending_cap
    if cap is None:
        cap = float(cfg.get("databento", "spending_cap_usd", default=0.0) or 0.0)
    adapter = DatabentoAdapter(root=cfg.project_root)
    layout = ensure_data_layout(cfg.project_root, cfg.get("paths", "data_dir", default="data"))
    result = adapter.download(
        request,
        download_enabled=enabled,
        approved=bool(args.i_approve_this_exact_request),
        spending_cap_usd=float(cap),
        acknowledge_prior_failure=bool(args.acknowledge_prior_failure),
        expected_fingerprint=expected_fp,
        raw_dir=layout["raw"],
    )
    raw_path = result.get("raw_path")
    if result.get("state") == "completed" and raw_path:
        from level_probability_lab.ingest import ohlcv_from_dbn_file
        from level_probability_lab.storage import write_parquet

        parquet_path = Path(raw_path).with_name(Path(raw_path).name.split(".dbn")[0] + ".parquet")
        raw = ohlcv_from_dbn_file(Path(raw_path))
        write_parquet(raw, parquet_path)
        result["raw_parquet"] = str(parquet_path)
        result["n_raw_rows"] = int(len(raw))
        result["symbols_in_file"] = sorted(raw["symbol"].astype(str).unique().tolist())
    _print_json(result)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    layout = ensure_data_layout(cfg.project_root, cfg.get("paths", "data_dir", default="data"))
    source = Path(args.input) if args.input else layout["smoke"] / "raw_synthetic.parquet"
    out_dir = Path(args.out_dir) if args.out_dir else layout["reports"] / "validate"
    is_synthetic = bool(args.synthetic) or "synthetic" in source.name
    result = run_validate_and_label(cfg, source, out_dir, is_synthetic=is_synthetic)
    _print_json(result)
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    cfg = _cfg(args)
    layout = ensure_data_layout(cfg.project_root, cfg.get("paths", "data_dir", default="data"))
    source = Path(args.input) if args.input else layout["smoke"] / "raw_synthetic.parquet"
    out_dir = Path(args.out_dir) if args.out_dir else layout["labels"]
    is_synthetic = bool(args.synthetic) or "synthetic" in source.name
    result = run_validate_and_label(cfg, source, out_dir, is_synthetic=is_synthetic)
    _print_json(result)
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    import pytest

    root = Path(args.project_root) if args.project_root else project_root()
    extra = list(args.pytest_args or [])
    return pytest.main([str(root / "tests"), *extra])


def cmd_ghost_replay(args: argparse.Namespace) -> int:
    from level_probability_lab.ghost_candles.run import run_ghost_replay

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


def cmd_ghost_eval(args: argparse.Namespace) -> int:
    from level_probability_lab.ghost_candles.experiment import run_experiment

    run_experiment()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="level_probability_lab",
        description="Level Probability Lab — research/paper-testing pipeline. No live trading.",
    )
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--config", default=None, help="YAML config path (relative to project root unless absolute)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_smoke = sub.add_parser("smoke", help="Offline synthetic pipeline (no API key, no network).")
    p_smoke.add_argument("--config", default="configs/smoke.yaml")
    p_smoke.set_defaults(func=cmd_smoke)

    p_quote = sub.add_parser("quote", help="Metadata-only Databento quote. Does not download market data.")
    p_quote.add_argument("--config", default="configs/databento_pilot.yaml")
    p_quote.set_defaults(func=cmd_quote)

    p_dl = sub.add_parser("download", help="Guarded download. Disabled unless explicitly approved.")
    p_dl.add_argument("--enable-download", action="store_true")
    p_dl.add_argument("--i-approve-this-exact-request", action="store_true")
    p_dl.add_argument("--spending-cap", type=float, default=None)
    p_dl.add_argument("--quote-manifest", default=None)
    p_dl.add_argument("--expected-fingerprint", default=None)
    p_dl.add_argument("--acknowledge-prior-failure", action="store_true")
    p_dl.add_argument("--config", default="configs/databento_pilot.yaml")
    p_dl.set_defaults(func=cmd_download)

    p_val = sub.add_parser("validate", help="Normalize and validate local OHLCV, then write a report.")
    p_val.add_argument("--input", default=None, help="Raw parquet with ts_event/OHLCV")
    p_val.add_argument("--out-dir", default=None)
    p_val.add_argument("--synthetic", action="store_true")
    p_val.add_argument("--config", default="configs/default.yaml")
    p_val.set_defaults(func=cmd_validate)

    p_lab = sub.add_parser("label", help="Validate local data and build event labels.")
    p_lab.add_argument("--input", default=None)
    p_lab.add_argument("--out-dir", default=None)
    p_lab.add_argument("--synthetic", action="store_true")
    p_lab.add_argument("--config", default="configs/default.yaml")
    p_lab.set_defaults(func=cmd_label)

    p_test = sub.add_parser("test", help="Run the unit test suite (pytest).")
    p_test.add_argument("pytest_args", nargs=argparse.REMAINDER)
    p_test.set_defaults(func=cmd_test)

    p_ghost = sub.add_parser("ghost-replay", help="Historical QQQ 5-minute Kronos ghost-candle replay.")
    p_ghost.add_argument("--session", default="2026-08-14")
    p_ghost.add_argument("--lookback", type=int, default=120)
    p_ghost.add_argument("--horizon", type=int, default=5)
    p_ghost.add_argument("--samples", type=int, default=50)
    p_ghost.add_argument("--seed", type=int, default=42)
    p_ghost.add_argument("--input", default=None)
    p_ghost.add_argument("--out-dir", default=None)
    p_ghost.add_argument("--kronos-root", default=r"C:\Users\ruley\Kronos")
    p_ghost.set_defaults(func=cmd_ghost_replay)

    p_eval = sub.add_parser("ghost-eval", help="Pooled QQQ ghost-candle evaluation (no new data purchase).")
    p_eval.set_defaults(func=cmd_ghost_eval)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except LabError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
