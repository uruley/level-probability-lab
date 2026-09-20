"""Create a readable result report after the frozen study has completed."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from level_probability_lab.baseline_study import CONFIG, ROOT


def main():
    root = ROOT / "data/kronos_baseline_v1"
    progress = json.loads((root/"progress.json").read_text())
    if progress["status"] != "complete":
        raise RuntimeError("All forecasts must be locked and scored before summarizing")
    frame = pd.read_csv(root/"scores.csv")
    report = json.loads((root/"report.json").read_text())
    probabilistic = []
    for (split, model, horizon), group in frame.groupby(["split", "model", "horizon"]):
        blocks = group.assign(delta=group.brier-group.climatology_brier).groupby("date").delta.agg(["sum", "count"])
        rng = np.random.default_rng(CONFIG["bootstrap_seed"])
        ix = rng.integers(0,len(blocks),size=(CONFIG["bootstrap_replicates"],len(blocks)))
        values = blocks["sum"].to_numpy()[ix].sum(axis=1)/blocks["count"].to_numpy()[ix].sum(axis=1)
        probabilistic.append(dict(split=split, model=model, horizon=int(horizon),
            brier_difference=float(blocks["sum"].sum()/blocks["count"].sum()),
            ci95=np.quantile(values,[.025,.975]).tolist(), sessions=len(blocks)))
    (root/"probability_comparisons.json").write_text(json.dumps(probabilistic,indent=2),encoding="utf-8")
    lines = ["# Frozen Kronos baseline study", "", "May 2026 development; June 2026 validation; July remains sealed.", "",
        "2,214 eligible origins, 25 paths per model/origin, five close horizons. No weight updates or setting search.", "",
        "## June validation", "", "| Model | Horizon | MAE ($) | Flat-price MAE ($) | MAE difference 95% session CI | Direction accuracy (calls) | 10–90 coverage | Brier / May climatology |",
        "|---|---:|---:|---:|---|---|---:|---|"]
    for row in report["metrics"]:
        if row["split"] != "validation":
            continue
        accuracy = "undefined" if row["direction_accuracy"] is None else f'{row["direction_accuracy"]:.1%}'
        lines.append(f'| {row["model"]} | +{row["horizon"]} | {row["mae"]:.4f} | {row["persistence_mae"]:.4f} | [{row["ci95"][0]:.4f}, {row["ci95"][1]:.4f}] | {accuracy} ({row["direction_n"]}) | {row["coverage_10_90"]:.1%} | {row["brier"]:.4f} / {row["climatology_brier"]:.4f} |')
    lines.extend(["", "Negative error differences favor Kronos. Session resampling preserves paired forecasts; these are descriptive, unadjusted intervals across multiple horizons.", "",
        "Probability comparisons with paired session-bootstrap intervals are in `probability_comparisons.json`. May is not an independent test of its own climatology.", "", "## Limits", ""])
    lines.extend("- "+x for x in report["limits"])
    (root/"RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(root/"RESULTS.md")


if __name__ == "__main__":
    main()
