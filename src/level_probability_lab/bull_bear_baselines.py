"""Stage 2 descriptive same-origin baseline summary.

This deliberately reports hard class predictions, not calibrated probabilities.
The existing replay ledger only stores binary-up probabilities, so those are
not relabeled as bull/neutral/bear probabilities here.
"""
from pathlib import Path
import json
import pandas as pd

from .bull_bear_truth import SPEC


def label_return(origin_close, actual_close, threshold=0.001):
    value = float(actual_close) / float(origin_close) - 1.0
    if value > threshold:
        return "bull"
    if value < -threshold:
        return "bear"
    return "neutral"


def summarize(scores, horizon=5, threshold=0.001):
    frame = scores.loc[scores.horizon_minutes == horizon].copy()
    frame["actual_class"] = [label_return(a, b, threshold) for a, b in
                              zip(frame.origin_close, frame.actual_close)]
    # The median Kronos/analogue close supplies a descriptive hard class only.
    frame["predicted_class"] = [label_return(a, b, threshold) for a, b in
                                zip(frame.origin_close, frame.median_close)]
    rows = []
    for engine, group in frame.groupby("engine", sort=True):
        rows.append({
            "engine": engine, "horizon_minutes": horizon,
            "n": int(len(group)), "sessions": int(group.session_date.nunique()),
            "actual_counts": group.actual_class.value_counts().reindex(
                ["bull", "neutral", "bear"], fill_value=0).astype(int).to_dict(),
            "predicted_counts": group.predicted_class.value_counts().reindex(
                ["bull", "neutral", "bear"], fill_value=0).astype(int).to_dict(),
            "hard_class_accuracy": float((group.actual_class == group.predicted_class).mean()),
            "mae": float(group.median_close_abs_error.mean()),
            "persistence_mae": float(abs(group.actual_close-group.origin_close).mean()),
        })
    return {"schema_version": "qqq_bull_bear_baseline_v1", "label_spec": SPEC,
            "threshold": threshold, "horizon_minutes": horizon,
            "probability_status": "not_available", "rows": rows}


def run(input_path, output_path):
    result = summarize(pd.read_parquet(input_path))
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result
