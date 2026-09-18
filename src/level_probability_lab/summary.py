from __future__ import annotations

from collections import Counter

import pandas as pd

from level_probability_lab.labeling import ALL_LABELS, QUALITY_STATUSES, VALID_CLASSES


SYNTHETIC_BANNER = (
    "SYNTHETIC plumbing test — not market evidence, not trading performance, "
    "and not a probability-model score."
)


def label_summary(labels: pd.DataFrame, *, is_synthetic: bool) -> dict:
    counts = {name: 0 for name in ALL_LABELS}
    if not labels.empty and "label" in labels.columns:
        counts.update(Counter(labels["label"].tolist()))
    total = int(sum(counts.values()))
    valid_n = int(sum(counts[k] for k in VALID_CLASSES))
    quality_n = int(sum(counts[k] for k in QUALITY_STATUSES))
    reasons: dict[str, int] = {}
    if not labels.empty and "reason" in labels.columns:
        reasons = dict(Counter(labels["reason"].fillna("").tolist()))

    def _prop(n: int) -> float | None:
        return None if total == 0 else n / total

    payload = {
        "disclaimer": SYNTHETIC_BANNER if is_synthetic else (
            "Research labels only. Reaching a threshold does not prove a fill or a profitable strategy."
        ),
        "is_synthetic": bool(is_synthetic),
        "n_rows": total,
        "counts": counts,
        "proportions_of_all_rows": {k: _prop(v) for k, v in counts.items()},
        "valid_class_total": valid_n,
        "quality_status_total": quality_n,
        "valid_class_share_of_all_rows": _prop(valid_n),
        "quality_share_of_all_rows": _prop(quality_n),
        "incomplete_and_ambiguous_are_not_neither": True,
        "reasons": reasons,
    }
    if not labels.empty and "context_stale" in labels.columns:
        payload["n_context_stale"] = int(labels["context_stale"].fillna(False).sum())
    if not labels.empty and "is_synthetic" in labels.columns:
        payload["all_rows_marked_synthetic"] = bool(labels["is_synthetic"].all())
    return payload
