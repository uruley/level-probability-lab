"""Label-builder audit and development-only barrier grid on August 2026."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from level_probability_lab.config import load_config
from level_probability_lab.labeling import ALL_LABELS, VALID_CLASSES, build_labels
from level_probability_lab.paths import ensure_data_layout, project_root
from level_probability_lab.storage import write_json


def _cfg_get(base_get, k_up: float, k_down: float):
    def getter(*keys, default=None):
        if keys == ("boundaries", "k_up"):
            return k_up
        if keys == ("boundaries", "k_down"):
            return k_down
        return base_get(*keys, default=default)

    return getter


def _counts(labels: pd.DataFrame) -> dict:
    n = int(len(labels))
    vc = labels["label"].value_counts().to_dict() if n else {}
    counts = {name: int(vc.get(name, 0)) for name in ALL_LABELS}
    valid_n = int(sum(counts[c] for c in VALID_CLASSES))
    quality_n = n - valid_n
    reasons = labels["reason"].value_counts().to_dict() if n else {}
    return {
        "n_prediction_times": n,
        "counts": counts,
        "denominators": {
            "all_prediction_times": n,
            "valid_class_rows": valid_n,
            "quality_status_rows": quality_n,
        },
        "proportions_of_all_prediction_times": {
            k: (v / n if n else None) for k, v in counts.items()
        },
        "proportions_of_valid_classes_only": {
            k: (counts[k] / valid_n if valid_n else None) for k in VALID_CLASSES
        },
        "reasons": {str(k): int(v) for k, v in reasons.items()},
        "ambiguous_not_recoded_as_neither": True,
        "incomplete_not_recoded_as_neither": True,
    }


def _distance_stats(labels: pd.DataFrame) -> dict:
    ok = labels[labels["vol_scale"].notna() & labels["reference_price"].notna()].copy()
    if ok.empty:
        return {}
    ok["half_width_usd"] = ok["upper"] - ok["reference_price"]
    ok["half_width_pct"] = 100.0 * ok["half_width_usd"] / ok["reference_price"]
    def qstats(s):
        return {
            "mean": float(s.mean()),
            "p10": float(s.quantile(0.10)),
            "p50": float(s.quantile(0.50)),
            "p90": float(s.quantile(0.90)),
        }
    return {
        "n_with_boundaries": int(len(ok)),
        "reference_price_usd": qstats(ok["reference_price"]),
        "vol_log_1min_sample_std": qstats(ok["vol_log"]),
        "half_width_usd": qstats(ok["half_width_usd"]),
        "half_width_pct_of_price": qstats(ok["half_width_pct"]),
        "k_times_1min_sigma_equals_sqrt15_note": (
            "If 1-minute log returns were iid, a 15-minute 1-sigma move is about "
            "sqrt(15)≈3.87 one-minute sigmas. k is a multiple of the 1-minute "
            "sigma, not of a 15-minute sigma."
        ),
    }


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs" / "databento_pilot.yaml", root=root)
    layout = ensure_data_layout(root, "data")
    norm_path = root / "data" / "labels" / "pilot_aug2026" / "normalized.parquet"
    labels_path = root / "data" / "labels" / "pilot_aug2026" / "labels.parquet"
    norm = pd.read_parquet(norm_path)
    labels_k1 = pd.read_parquet(labels_path)

    # Integrity checks on the inspected August sample.
    qqq = norm[norm["symbol"] == "QQQ"]
    rth = qqq[qqq["is_regular_session"]]
    integrity = {
        "normalized_path": str(norm_path),
        "symbols": sorted(norm["symbol"].astype(str).unique().tolist()),
        "session_dates": sorted({str(pd.Timestamp(d).date()) for d in rth["session_date"].dropna()}),
        "n_sessions": int(rth["session_date"].nunique()),
        "rth_minutes_by_symbol": {
            str(sym): int(((norm["symbol"] == sym) & (norm["is_regular_session"])).sum())
            for sym in norm["symbol"].unique()
        },
        "bar_status_counts": norm.groupby("bar_status").size().to_dict(),
        "duplicate_symbol_bar_start": int(norm.duplicated(["symbol", "bar_start"]).sum()),
        "coverage_gap_rows": int((norm["bar_status"] == "coverage_gap").sum()),
        "no_trade_rows": int((norm["bar_status"] == "no_trade").sum()),
        "discontinuity_candidates": int(norm["discontinuity_candidate"].sum())
        if "discontinuity_candidate" in norm.columns
        else None,
        "context_nvda_stale": int(labels_k1["context_stale"].fillna(False).sum())
        if "context_stale" in labels_k1.columns
        else None,
        "context_tsla_stale": int(labels_k1["context_tsla_stale"].fillna(False).sum())
        if "context_tsla_stale" in labels_k1.columns
        else None,
        "lookback_last_start_le_prediction": bool(
            (
                labels_k1["lookback_last_start"].isna()
                | (labels_k1["lookback_last_start"] <= labels_k1["prediction_bar_start"])
            ).all()
        ),
        "horizon_is_15_elapsed_minutes": bool(
            (
                (labels_k1["horizon_end"] - labels_k1["horizon_start"])
                == pd.Timedelta(minutes=15)
            ).all()
        ),
        "prediction_time_equals_bar_end_plus_lag": bool(
            (labels_k1["prediction_time"] == labels_k1["prediction_bar_end"]).all()
        ),
    }

    formula = {
        "target": "QQQ",
        "feed": "XNAS.ITCH Nasdaq venue prints; not SIP/consolidated",
        "bar": "1-minute OHLCV; ts_event is bar start; bar is complete at bar_end",
        "usable_at": "bar_end + assumed publication_lag_seconds (0). Not an exchange publication timestamp.",
        "lookback": (
            "Same regular session only. Observed QQQ closes with bar_start in "
            "[prediction_bar_start - 119 minutes, prediction_bar_start], i.e. 120 "
            "completed 1-minute bars including the prediction bar when all minutes exist."
        ),
        "min_observed_for_vol": 60,
        "vol_log": "sample standard deviation (ddof=1) of 1-minute log returns log(c_t/c_{t-1}) on lookback closes",
        "vol_scale_usd": "abs(reference_close) * vol_log",
        "k": "dimensionless multiplier of vol_scale. Default k_up = k_down = 1.0 in Phase 1 config.",
        "upper": "reference_close + k_up * vol_scale  (frozen at prediction time)",
        "lower": "reference_close - k_down * vol_scale  (frozen at prediction time)",
        "horizon": (
            "15 elapsed minutes after bar_end, same regular session. Expected minute "
            "grid is 15 bars with start in [bar_end, bar_end+15 minutes). Not 'next 15 rows'."
        ),
        "path_rule": (
            "Walk those minutes in order. no_trade minutes do not touch. If a bar's high "
            "and low both reach the frozen bounds, label is ambiguous (order unknown). "
            "Never infer tick path from OHLC."
        ),
        "incomplete_reasons": [
            "insufficient_lookback",
            "vol_undefined",
            "degenerate_boundaries",
            "horizon_beyond_session",
            "missing_horizon_bar",
            "coverage_gap",
        ],
        "execution_disclaimer": (
            "A high or low print on Nasdaq does not prove an order would have filled "
            "or that a strategy is profitable."
        ),
    }

    k_grid = [1.0, 2.0, 3.0, 4.0, 5.0]
    grid = []
    for k in k_grid:
        labeled = build_labels(norm, _cfg_get(cfg.get, k, k))
        valid = labeled[labeled["label"].isin(VALID_CLASSES)]
        row = {
            "k_up": k,
            "k_down": k,
            "definition": "upper=ref+k*|ref|*std(1min log returns); lower=ref-k*|ref|*std(...)",
            "counts": _counts(labeled),
            "distance_on_rows_with_boundaries": _distance_stats(labeled),
            "valid_class_balance_not_an_objective": True,
        }
        if not valid.empty:
            row["valid_class_empirical_frequencies"] = {
                c: float((valid["label"] == c).mean()) for c in VALID_CLASSES
            }
        grid.append(row)

    # Ambiguous sensitivity on k=1: if forced to a class, range of scores later.
    amb = int((labels_k1["label"] == "ambiguous").sum())
    n_all = int(len(labels_k1))
    n_valid = int(labels_k1["is_valid_class"].sum())
    sensitivity = {
        "k": 1.0,
        "n_ambiguous": amb,
        "share_of_all_prediction_times": amb / n_all if n_all else None,
        "if_dropped": {
            "remaining_n": n_all - amb,
            "note": "Dropping ambiguous is not the same as labeling them neither.",
        },
        "if_all_assigned_upper_first": "would add 53 to upper_first; do not do this in the primary score",
        "if_all_assigned_lower_first": "would add 53 to lower_first",
        "if_all_assigned_neither": "forbidden as a silent default; report only as a sensitivity case",
        "primary_protocol": (
            "Keep ambiguous and incomplete as non-class rows. Score Brier/log loss "
            "on valid classes only, and always publish quality-status counts."
        ),
    }

    payload = {
        "sample": "development_inspected_august_2026",
        "not_a_holdout": True,
        "nasdaq_feed_research": True,
        "formula": formula,
        "integrity": integrity,
        "k1_implemented_labels": _counts(labels_k1),
        "k1_distance": _distance_stats(labels_k1),
        "development_barrier_grid_k_times_1min_sigma": grid,
        "ambiguous_sensitivity_k1": sensitivity,
        "selection_rule_for_k": (
            "Do not pick k to equalize class counts. Prefer a k whose half-width is "
            "economically interpretable (dollars and percent of QQQ) and whose 15-minute "
            "neither rate is not degenerate. Freeze one k (or a small set of k) from this "
            "development grid, then compare all models at the same frozen k."
        ),
    }
    out = layout["reports"] / "label_audit_august2026.json"
    write_json(payload, out)
    print("sessions", integrity["n_sessions"])
    print("k1 counts", payload["k1_implemented_labels"]["counts"])
    print("k1 half-width usd p50", payload["k1_distance"].get("half_width_usd"))
    print("k1 half-width pct p50", payload["k1_distance"].get("half_width_pct_of_price"))
    for row in grid:
        c = row["counts"]["counts"]
        d = row["distance_on_rows_with_boundaries"]
        hw = d.get("half_width_usd", {})
        hp = d.get("half_width_pct_of_price", {})
        print(
            f"k={row['k_up']} valid={row['counts']['denominators']['valid_class_rows']} "
            f"U={c['upper_first']} L={c['lower_first']} N={c['neither']} "
            f"A={c['ambiguous']} I={c['incomplete']} "
            f"half$ p50={hw.get('p50')} half% p50={hp.get('p50')}"
        )
    print("saved", out)


if __name__ == "__main__":
    main()
