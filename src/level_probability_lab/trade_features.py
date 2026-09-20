"""Causal receive-time trade features; no network or data acquisition methods."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from level_probability_lab.calendar import expected_regular_minutes, session_schedule

FEATURES = ["trade_count", "mean_size", "max_size_fraction", "size_cv",
            "vwap_close_bps", "within_minute_realized_var",
            "known_signed_fraction", "unknown_fraction"]


def normalize_trades(frame: pd.DataFrame, *, price_type: str = "float") -> pd.DataFrame:
    """Normalize explicit DBN price representation; never guess integer scaling."""
    out = frame.reset_index() if "ts_recv" not in frame.columns else frame.copy()
    required = {"ts_recv", "price", "size", "side", "flags"}
    if not required.issubset(out):
        raise ValueError(f"missing trade fields: {sorted(required - set(out))}")
    out["ts_recv"] = pd.to_datetime(out["ts_recv"], utc=True)
    if out["ts_recv"].isna().any():
        raise ValueError("missing receive timestamp")
    if price_type not in {"float", "fixed"}:
        raise ValueError("price_type must be float or fixed")
    out["price"] = pd.to_numeric(out["price"], errors="raise").astype(float)
    if price_type == "fixed":
        out["price"] /= 1e9
    out["size"] = pd.to_numeric(out["size"], errors="raise").astype(float)
    out["flags"] = out["flags"].astype("uint8")
    out["side"] = out["side"].map(lambda x: x.decode() if isinstance(x, bytes) else str(x))
    if not out["side"].isin(["A", "B", "N"]).all():
        raise ValueError("unexpected trade side")
    out["bar_start"] = out["ts_recv"].dt.floor("min")
    return out.sort_values("ts_recv", kind="stable").reset_index(drop=True)


def minute_features(frame: pd.DataFrame, *, price_type: str = "float") -> pd.DataFrame:
    """One row per received minute; corrupt minutes retained but made ineligible."""
    t = normalize_trades(frame, price_type=price_type)
    valid = np.isfinite(t.price) & (t.price > 0) & (t.price < 9e9) & np.isfinite(t["size"]) & (t["size"] > 0)
    # BAD_TS_RECV=8 and MAYBE_BAD_BOOK=4: reject whole affected minutes.
    t["bad_record"] = ~valid | ((t["flags"].to_numpy() & 12) != 0)
    t["dollar"] = t.price * t["size"]
    t["signed_size"] = t["size"] * t.side.map({"B": 1, "A": -1, "N": 0})
    t["unknown_size"] = t["size"] * (t.side == "N")
    t["log_price"] = np.log(t.price.where(valid))
    t["squared_return"] = t.groupby("bar_start", sort=False).log_price.diff().pow(2)
    g = t.groupby("bar_start", sort=True)
    out = g.agg(open=("price", "first"), high=("price", "max"), low=("price", "min"),
                close=("price", "last"), volume=("size", "sum"), trade_count=("size", "size"),
                mean_size=("size", "mean"), max_size=("size", "max"), size_std=("size", lambda x: x.std(ddof=0)),
                dollars=("dollar", "sum"), signed=("signed_size", "sum"), unknown=("unknown_size", "sum"),
                within_minute_realized_var=("squared_return", "sum"), bad_records=("bad_record", "sum"),
                last_received_at=("ts_recv", "max"))
    out["max_size_fraction"] = out.max_size / out.volume
    out["size_cv"] = out.size_std / out.mean_size
    out["vwap_close_bps"] = (out.dollars / out.volume / out.close - 1) * 1e4
    out["known_signed_fraction"] = out.signed / out.volume
    out["unknown_fraction"] = out.unknown / out.volume
    out["available_at"] = out.index + pd.Timedelta(minutes=1)
    out["feature_eligible"] = out.bad_records == 0
    out.loc[~out.feature_eligible, FEATURES] = np.nan
    return out.drop(columns=["max_size", "size_std", "dollars", "signed", "unknown"]).reset_index()


def build_local(raw_path: Path, history_path: Path, output: Path, *,
                unseal_holdout: bool = False, frozen_comparison: Path | None = None) -> dict:
    """Read only May/June price values; July filtered by timestamp before feature use."""
    import databento as db
    if unseal_holdout:
        if frozen_comparison is None or not frozen_comparison.is_file():
            raise ValueError("July requires an existing frozen comparator artifact")
        from level_probability_lab.trade_comparison import require_frozen
        if frozen_comparison.name != "frozen_model.json":
            raise ValueError("expected frozen_model.json comparator artifact")
        require_frozen(frozen_comparison.parent)
    start = pd.Timestamp("2026-07-01" if unseal_holdout else "2026-05-01", tz="UTC")
    end = pd.Timestamp("2026-08-01" if unseal_holdout else "2026-07-01", tz="UTC")
    suffix = "july" if unseal_holdout else "may_june"
    store = db.DBNStore.from_file(raw_path)
    parts, columns = [], None
    for chunk in store.to_df(price_type="float", pretty_ts=True, count=250000):
        columns = list(chunk.columns)
        recv = chunk.index if chunk.index.name == "ts_recv" else pd.to_datetime(chunk.ts_recv, utc=True)
        selected = chunk.loc[(recv >= start) & (recv < end)]
        if len(selected):
            if "symbol" not in selected or not (selected.symbol == "QQQ").all():
                raise ValueError("trade source must contain only mapped QQQ records")
            fields = ["price", "size", "side", "flags"]
            if "ts_recv" in selected.columns:
                fields.insert(0, "ts_recv")
            parts.append(selected[fields].copy())
    t = normalize_trades(pd.concat(parts))
    grid = expected_regular_minutes(session_schedule(start, end - pd.Timedelta(days=1)))
    t = t.loc[t.bar_start.isin(grid)].copy()
    bars = minute_features(t)
    # Read historical prices only for matching May/June; no July outcome inspection.
    history = pd.read_parquet(history_path, filters=[("symbol", "==", "QQQ"), ("ts_event", ">=", start), ("ts_event", "<", end)])
    stamp = pd.to_datetime(history["ts_event"], utc=True)
    history = history.loc[(stamp >= start) & (stamp < end)].copy()
    history["bar_start"] = pd.to_datetime(history.ts_event, utc=True)
    history = history.loc[history.bar_start.isin(grid)]
    joined = bars.merge(history[["bar_start", "open", "high", "low", "close", "volume"]], on="bar_start", suffixes=("_trades", "_bars"), how="outer", indicator=True)
    mismatch = {}
    both = joined["_merge"] == "both"
    any_mismatch = ~both
    for col in ["open", "high", "low", "close", "volume"]:
        bad = both & ~np.isclose(joined[col + "_trades"], joined[col + "_bars"], atol=1e-7 if col != "volume" else 0, rtol=0)
        mismatch[col] = int(bad.sum())
        any_mismatch |= bad
    bad_minutes = set(joined.loc[any_mismatch, "bar_start"])
    bars["reconciled"] = ~bars.bar_start.isin(bad_minutes)
    bars["feature_eligible"] &= bars.reconciled
    bars.loc[~bars.feature_eligible, FEATURES] = np.nan
    output.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(output / f"trade_features_{suffix}.parquet", index=False)
    joined.loc[any_mismatch].to_parquet(output / f"reconciliation_mismatches_{suffix}.parquet", index=False)
    def sha256(path):
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    report = {"accepted": bool(bars.feature_eligible.any() and not bars.bar_start.duplicated().any()
                              and (bars.last_received_at < bars.available_at).all()),
              "raw_sha256": sha256(raw_path), "history_sha256": sha256(history_path),
              "features_sha256": sha256(output / f"trade_features_{suffix}.parquet"),
              "producer_sha256": sha256(Path(__file__)),
              "frozen_comparison_sha256": sha256(frozen_comparison) if unseal_holdout else None,
              "quality_policy": "Reject minute if flags & 12, invalid price/size, or any OHLCV mismatch; no imputation",
              "raw_schema_fields": list(dict.fromkeys(["ts_recv", *columns])), "price_representation": "DBN to_df float", "months_processed": ["2026-07"] if unseal_holdout else ["2026-05", "2026-06"],
              "july_outcomes_inspected": unseal_holdout, "regular_trade_rows": len(t), "minute_rows": len(bars),
              "expected_regular_minutes": len(grid), "missing_trade_minutes": len(grid.difference(bars.bar_start)),
              "eligible_minutes": int(bars.feature_eligible.sum()), "mismatches": mismatch,
              "join_counts": joined["_merge"].value_counts().to_dict(), "side_counts": t.side.value_counts().to_dict(),
              "unknown_volume_fraction": float(t.loc[t.side == "N", "size"].sum() / t["size"].sum()),
              "flag_counts": {str(k): int(v) for k,v in t["flags"].value_counts().items()},
              "bad_timestamp_records": int(((t["flags"].to_numpy() & 8) != 0).sum()),
              "possible_gap_records": int(((t["flags"].to_numpy() & 4) != 0).sum())}
    audit_name = "trade_feature_audit_july.json" if unseal_holdout else "trade_feature_audit.json"
    (output / audit_name).write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("data/trades_study"))
    p.add_argument("--unseal-holdout", action="store_true")
    p.add_argument("--frozen-comparison", type=Path)
    args = p.parse_args()
    print(json.dumps(build_local(args.raw, args.history, args.output,
                                unseal_holdout=args.unseal_holdout,
                                frozen_comparison=args.frozen_comparison), indent=2))
