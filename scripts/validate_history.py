"""Validate the multi-year XNAS.ITCH OHLCV file. No model fitting."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from level_probability_lab.calendar import early_close_session_dates, session_schedule
from level_probability_lab.paths import ensure_data_layout, project_root
from level_probability_lab.storage import write_json

RAW_PATH = Path("data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet")
REQUEST_START = pd.Timestamp("2018-05-01T00:00:00Z")
REQUEST_END = pd.Timestamp("2026-09-01T00:00:00Z")
DEGRADED = [date(2021, 7, 7), date(2021, 10, 26), date(2022, 9, 19)]
KNOWN_SPLITS = [
    {"symbol": "TSLA", "date": "2020-08-31", "ratio": 5.0},
    {"symbol": "TSLA", "date": "2022-08-25", "ratio": 3.0},
    {"symbol": "NVDA", "date": "2024-06-10", "ratio": 10.0},
]
PARTITIONS = {
    "train": ("2018-05-01", "2023-12-29"),
    "validation_calibration": ("2024-01-02", "2024-12-31"),
    "protected_holdout": ("2025-01-02", "2026-07-31"),
    "development_inspected": ("2026-08-03", "2026-08-31"),
}


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def attach_sessions(raw: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    sess = schedule.reset_index()
    sess = sess.rename(columns={sess.columns[0]: "session_date"})
    sess["session_date"] = pd.to_datetime(sess["session_date"]).dt.tz_localize(None)
    sess["market_open"] = pd.to_datetime(sess["market_open"], utc=True).astype("datetime64[ns, UTC]")
    sess["market_close"] = pd.to_datetime(sess["market_close"], utc=True).astype("datetime64[ns, UTC]")
    sess = sess.sort_values("market_open")
    work = raw.sort_values("ts_event")
    work["ts_event"] = pd.to_datetime(work["ts_event"], utc=True).astype("datetime64[ns, UTC]")
    merged = pd.merge_asof(
        work,
        sess[["session_date", "market_open", "market_close"]],
        left_on="ts_event",
        right_on="market_open",
        direction="backward",
    )
    in_rth = merged["market_open"].notna() & (merged["ts_event"] >= merged["market_open"]) & (
        merged["ts_event"] < merged["market_close"]
    )
    merged["is_regular_session"] = in_rth
    merged.loc[~in_rth, "session_date"] = pd.NaT
    return merged


def overnight_moves(rth: pd.DataFrame, symbol: str) -> pd.DataFrame:
    sub = rth[rth["symbol"] == symbol].sort_values("ts_event")
    if sub.empty:
        return pd.DataFrame()
    first = sub.groupby("session_date", sort=True).first()
    last = sub.groupby("session_date", sort=True).last()
    prev_close = last["close"].shift(1)
    move = np.log(first["open"] / prev_close)
    out = pd.DataFrame(
        {
            "session_date": first.index,
            "open": first["open"].to_numpy(),
            "prev_close": prev_close.to_numpy(),
            "log_return": move.to_numpy(),
        }
    )
    return out.dropna()


def main() -> None:
    root = project_root()
    layout = ensure_data_layout(root, "data")
    path = root / RAW_PATH
    raw = pd.read_parquet(path)
    errors: list[str] = []
    warnings: list[str] = []

    raw["ts_event"] = pd.to_datetime(raw["ts_event"], utc=True)
    n = len(raw)
    symbols = sorted(raw["symbol"].astype(str).unique().tolist())

    if raw["ts_event"].dt.tz is None:
        errors.append("ts_event is not UTC-aware")
    if raw.duplicated(["symbol", "ts_event"]).any():
        errors.append(f"duplicate symbol/ts_event: {int(raw.duplicated(['symbol','ts_event']).sum())}")
    if raw["volume"].isna().any():
        errors.append("null volume")
    if (raw["volume"] < 0).any():
        errors.append("negative volume")
    ohlc_ok = (
        (raw["low"] <= raw["open"])
        & (raw["low"] <= raw["close"])
        & (raw["low"] <= raw["high"])
        & (raw["high"] >= raw["open"])
        & (raw["high"] >= raw["close"])
    )
    bad_ohlc = int((~ohlc_ok).sum())
    if bad_ohlc:
        errors.append(f"OHLC inconsistency: {bad_ohlc}")
    if raw[["open", "high", "low", "close"]].isna().any().any():
        errors.append("NaN OHLC")
    if raw["ts_event"].min() < REQUEST_START:
        warnings.append("rows before request start")
    if raw["ts_event"].max() >= REQUEST_END:
        errors.append("rows at or after exclusive request end")
    for sym in ("NVDA", "QQQ", "TSLA"):
        if sym not in symbols:
            errors.append(f"missing symbol {sym}")
    for sym, grp in raw.groupby("symbol"):
        if not grp["ts_event"].is_monotonic_increasing:
            errors.append(f"{sym} timestamps not sorted")

    schedule = session_schedule("2018-05-01", "2026-08-31", "NYSE")
    early = sorted(early_close_session_dates(schedule, "NYSE"))
    tagged = attach_sessions(raw, schedule)
    rth = tagged[tagged["is_regular_session"]].copy()
    rth["session_date"] = pd.to_datetime(rth["session_date"]).dt.tz_localize(None)

    expected_minutes = (
        (schedule["market_close"] - schedule["market_open"]).dt.total_seconds() / 60
    ).astype(int)
    expected_minutes.index = pd.to_datetime(schedule.index).tz_localize(None)

    coverage = {}
    missing_sessions = {}
    short_sessions = {}
    for sym in ("NVDA", "QQQ", "TSLA"):
        counts = rth[rth["symbol"] == sym].groupby("session_date").size()
        counts.index = pd.to_datetime(counts.index).tz_localize(None)
        aligned = expected_minutes.to_frame("expected").join(counts.to_frame("observed"), how="left")
        aligned["observed"] = aligned["observed"].fillna(0).astype(int)
        missing = aligned[aligned["observed"] == 0]
        short = aligned[(aligned["observed"] > 0) & (aligned["observed"] < aligned["expected"])]
        extra = aligned[aligned["observed"] > aligned["expected"]]
        coverage[sym] = {
            "rth_bars": int(aligned["observed"].sum()),
            "expected_rth_bars": int(aligned["expected"].sum()),
            "sessions_with_any_bar": int((aligned["observed"] > 0).sum()),
            "nyse_sessions": int(len(aligned)),
            "missing_sessions": int(len(missing)),
            "short_sessions": int(len(short)),
            "sessions_over_expected": int(len(extra)),
            "missing_session_dates": [str(d.date()) for d in missing.index[:20]],
            "worst_shortfalls": [
                {"date": str(idx.date()), "observed": int(row.observed), "expected": int(row.expected)}
                for idx, row in short.sort_values("observed").head(10).iterrows()
            ],
        }
        missing_sessions[sym] = [str(d.date()) for d in missing.index]
        short_sessions[sym] = int(len(short))

    degraded_detail = []
    for d in DEGRADED:
        day = pd.Timestamp(d)
        if day not in expected_minutes.index:
            degraded_detail.append({"date": str(d), "on_nyse_calendar": False})
            continue
        exp = int(expected_minutes.loc[day])
        row = {"date": str(d), "on_nyse_calendar": True, "expected_rth_minutes": exp, "symbols": {}}
        for sym in ("NVDA", "QQQ", "TSLA"):
            obs = int(
                ((rth["symbol"] == sym) & (pd.to_datetime(rth["session_date"]).dt.date == d)).sum()
            )
            row["symbols"][sym] = {"observed_rth": obs, "complete": obs == exp}
        degraded_detail.append(row)
        if any(not v["complete"] for v in row["symbols"].values()):
            warnings.append(f"degraded day {d} is incomplete on this file")

    split_report = []
    overnight = {sym: overnight_moves(rth, sym) for sym in ("NVDA", "QQQ", "TSLA")}
    for spec in KNOWN_SPLITS:
        moves = overnight[spec["symbol"]]
        day = pd.Timestamp(spec["date"])
        hit = moves[moves["session_date"] == day]
        expected_log = float(np.log(1.0 / spec["ratio"]))
        if hit.empty:
            split_report.append({**spec, "found": False})
            warnings.append(f"known split {spec} not found as session date")
            continue
        log_r = float(hit["log_return"].iloc[0])
        split_report.append(
            {
                **spec,
                "found": True,
                "open": float(hit["open"].iloc[0]),
                "prev_close": float(hit["prev_close"].iloc[0]),
                "log_return": log_r,
                "price_ratio_open_over_prev_close": float(hit["open"].iloc[0] / hit["prev_close"].iloc[0]),
                "expected_log_return_if_unadjusted": expected_log,
                "matches_unadjusted_split": bool(abs(log_r - expected_log) < 0.05),
            }
        )
    large_jumps = {}
    for sym, moves in overnight.items():
        big = moves[moves["log_return"].abs() >= 0.08].copy()
        large_jumps[sym] = [
            {
                "session_date": str(pd.Timestamp(r.session_date).date()),
                "log_return": float(r.log_return),
                "open": float(r.open),
                "prev_close": float(r.prev_close),
            }
            for r in big.itertuples(index=False)
        ]

    # As-of: QQQ RTH usable_at vs last NVDA/TSLA observed bar_end <= usable_at
    qqq = rth[rth["symbol"] == "QQQ"][["ts_event"]].copy()
    qqq["usable_at"] = qqq["ts_event"] + pd.Timedelta(minutes=1)
    asof = {}
    for ctx in ("NVDA", "TSLA"):
        other = rth[rth["symbol"] == ctx][["ts_event"]].copy()
        other["usable_at"] = other["ts_event"] + pd.Timedelta(minutes=1)
        other = other.sort_values("usable_at")
        left = qqq.sort_values("usable_at")
        joined = pd.merge_asof(
            left,
            other.rename(columns={"ts_event": "ctx_bar_start", "usable_at": "ctx_usable_at"}),
            left_on="usable_at",
            right_on="ctx_usable_at",
            direction="backward",
        )
        stale_s = (joined["usable_at"] - joined["ctx_usable_at"]).dt.total_seconds()
        future = joined["ctx_usable_at"].notna() & (joined["ctx_usable_at"] > joined["usable_at"])
        if future.any():
            errors.append(f"{ctx} as-of leaked future bars: {int(future.sum())}")
        asof[ctx] = {
            "qqq_rth_bars": int(len(joined)),
            "missing_context": int(joined["ctx_usable_at"].isna().sum()),
            "stale_over_60s": int((stale_s > 60).fillna(False).sum()),
            "median_staleness_seconds": float(stale_s.median()) if stale_s.notna().any() else None,
            "max_staleness_seconds": float(stale_s.max()) if stale_s.notna().any() else None,
            "future_leaks": int(future.sum()),
        }

    # Partition overlap: last train session close vs first val open, etc.
    overlap = {}
    ordered = [
        ("train", "validation_calibration"),
        ("validation_calibration", "protected_holdout"),
        ("protected_holdout", "development_inspected"),
    ]
    idx = pd.to_datetime(schedule.index).tz_localize(None)
    for left_name, right_name in ordered:
        l0, l1 = PARTITIONS[left_name]
        r0, r1 = PARTITIONS[right_name]
        left_sess = schedule[(idx >= pd.Timestamp(l0)) & (idx <= pd.Timestamp(l1))]
        right_sess = schedule[(idx >= pd.Timestamp(r0)) & (idx <= pd.Timestamp(r1))]
        last_close = pd.Timestamp(left_sess.iloc[-1]["market_close"])
        first_open = pd.Timestamp(right_sess.iloc[0]["market_open"])
        # Same-session 15-minute horizon after a bar ending at last_close-1min ends at last_close+14min
        # which is still <= last_close + 14min, compared to next open.
        latest_horizon_end = last_close + pd.Timedelta(minutes=14)
        overlap[f"{left_name}_to_{right_name}"] = {
            "left_last_close_utc": last_close.isoformat(),
            "right_first_open_utc": first_open.isoformat(),
            "latest_possible_same_session_horizon_end_utc": latest_horizon_end.isoformat(),
            "horizon_would_overlap_next_open": bool(latest_horizon_end > first_open),
        }

    payload = {
        "file": str(path),
        "nasdaq_feed_research": True,
        "not_consolidated_tape": True,
        "models_fit": False,
        "n_raw_rows": n,
        "symbols": symbols,
        "rows_by_symbol": {str(k): int(v) for k, v in raw.groupby("symbol").size().items()},
        "ts_min_utc": raw["ts_event"].min().isoformat(),
        "ts_max_utc": raw["ts_event"].max().isoformat(),
        "request_start_inclusive": REQUEST_START.isoformat(),
        "request_end_exclusive": REQUEST_END.isoformat(),
        "volume_null": int(raw["volume"].isna().sum()),
        "volume_zero": int((raw["volume"] == 0).sum()),
        "volume_min": int(raw["volume"].min()),
        "bad_ohlc": bad_ohlc,
        "duplicates": int(raw.duplicated(["symbol", "ts_event"]).sum()),
        "nyse_sessions_in_range": int(len(schedule)),
        "early_close_sessions": [str(d) for d in early],
        "rth_bars": int(len(rth)),
        "extended_or_unmatched_bars": int((~tagged["is_regular_session"]).sum()),
        "coverage_by_symbol": coverage,
        "degraded_days": degraded_detail,
        "known_splits_unadjusted_check": split_report,
        "overnight_log_abs_ge_0_08": large_jumps,
        "context_asof_qqq_rth": asof,
        "partition_horizon_overlap": overlap,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    out = layout["reports"] / "history_validation.json"
    write_json(payload, out)
    print("ok", payload["ok"])
    print("rows", n, "rth", payload["rth_bars"])
    print("errors", errors)
    print("warnings", warnings)
    for sym, c in coverage.items():
        print(
            f"{sym} missing_sessions={c['missing_sessions']} "
            f"short_sessions={c['short_sessions']} "
            f"rth={c['rth_bars']}/{c['expected_rth_bars']}"
        )
    print("saved", out)


if __name__ == "__main__":
    main()
