"""Produce a readable report from completed studies; never runs models or downloads."""
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/trade_comparison_v1"


def read(path):
    return json.loads((ROOT / path).read_text())


def render():
    result = read("data/trade_comparison_v1/holdout_report.json")
    baseline = read("data/kronos_baseline_v1/report.json")
    quality = read("data/trades_study/trade_feature_audit.json")
    final_quality = read("data/trades_study/trade_feature_audit_july.json")
    frozen = read("data/trade_comparison_v1/frozen_model.json")
    purchase = read("data/manifests/downloads/81b52cd2b2a9ffe4fabc51f79efe308f93884f4aecadc08f5a727d413de89239.json")
    names = {"raw_base": "Kronos Base", "raw_small": "Kronos Small", "persistence": "Unchanged price",
             "candle_control": "Base + candle correction", "trade_augmented": "Base + candle and trade correction"}
    primary = result["primary"]
    outcome = ("The prespecified incremental-value threshold was met on July."
               if primary["practical_threshold_met"] else
               "This test did not establish incremental predictive value from time-and-sales.")
    relative = primary["relative_mae_improvement"] * 100
    ci = primary["ci95"]
    lines = ["# QQQ three-month research results", "", outcome, "",
        "May 2026 was used for fitting, June for selecting regularization, and July for one frozen final test.", "",
        f"The final comparison contains **{result['matched_origins']:,} matched origins across {primary['sessions']} July sessions**.", "",
        "## Primary result: five-minute close error", "",
        f"Trade correction versus the same correction using candles only: **{relative:+.2f}% relative MAE improvement** (positive is better).",
        f"Paired mean error difference: **${primary['mae_difference']:+.5f}**, with session-bootstrap 95% interval **[${ci[0]:+.5f}, ${ci[1]:+.5f}]**. Negative differences favor trades.", "",
        "The predeclared requirement was at least 1% improvement and an interval entirely below zero.", "",
        "| Engine | July +5 minute MAE | July +5 minute RMSE |", "|---|---:|---:|"]
    for row in result["metrics"]:
        if row["horizon"] == 5:
            lines.append(f"| {names[row['arm']]} | ${row['mae']:.5f} | ${row['rmse']:.5f} |")
    lines += ["", "## Every forecast horizon", "",
        "| Horizon | Candle-control MAE | Trade-augmented MAE | Relative improvement | Paired 95% difference interval |",
        "|---|---:|---:|---:|---|"]
    for h in range(1, 6):
        rows = {r["arm"]: r for r in result["metrics"] if r["horizon"] == h}
        c = next(c for c in result["trade_vs_candle"] if c["horizon"] == h)
        lo, hi = c["ci95"]
        lines.append(f"| +{h} minute | ${rows['candle_control']['mae']:.5f} | ${rows['trade_augmented']['mae']:.5f} | {100*c['relative_mae_improvement']:+.2f}% | [{lo:+.5f}, {hi:+.5f}] |")
    lines += ["", "## June baseline, before the final test", "",
        "| Engine | +5 minute MAE | Flat-price MAE | Up-event Brier | May-climatology Brier | Sampled close interval coverage |",
        "|---|---:|---:|---:|---:|---:|"]
    for r in baseline["metrics"]:
        if r["split"] == "validation" and r["horizon"] == 5:
            lines.append(f"| Kronos {r['model'].title()} | ${r['mae']:.5f} | ${r['persistence_mae']:.5f} | {r['brier']:.5f} | {r['climatology_brier']:.5f} | {r['coverage_10_90']:.1%} |")
    lines += ["", "## Data, method, and limits", "",
        f"- Databento acquisition completed once under a $3 cap. Fresh quoted estimate: **${purchase['quoted_cost_usd']:.6f}**. Actual invoice is not exposed by the adapter.",
        f"- May/June quality check: {quality['minute_rows']:,} reconstructed minute bars; {sum(quality['mismatches'].values())} OHLCV field mismatches. Unknown-side volume: {quality['unknown_volume_fraction']:.2%}.",
        f"- July quality check: {final_quality['minute_rows']:,} minute bars; {sum(final_quality['mismatches'].values())} OHLCV field mismatches. Excluded test origins/sessions: {len(result['excluded_origins'])}.",
        f"- Ridge penalties selected on June: candle control {frozen['models']['candle_control']['alpha']:g}; trade augmentation {frozen['models']['trade_augmented']['alpha']:g}. Scalers and coefficients were fitted on May only.",
        "- Frozen Base and Small use 120 completed candles, 25 sampled paths, five elapsed-minute targets, and seed 42. Predictions and actual outcomes are saved in CSV.",
        "- All arms use identical eligible origins. The trade comparison uses the same Base forecast and correction family; it isolates incremental trade features.",
        "- Confidence intervals resample whole sessions (2,000 replicates); a single month and cross-session dependence limit generalization.",
        "- Direction metrics, where reported in JSON, exclude predicted and actual neutral moves. Unchanged price makes no directional call.",
        "- Nasdaq venue prints are not the consolidated tape. This is forecast research, not a profitability or execution claim.",
        "- No neural weights were trained and no LLM explanation layer was scored. July results must not be used for retuning this study.", "",
        "## Artifacts", "",
        "- `holdout_predictions.csv`: all five arms, actual and predicted closes, all horizons.",
        "- `development_validation_predictions.csv`: matched fitting/selection-period outputs.",
        "- `holdout_report.json`: all metrics, paired intervals, exclusions, and frozen model hash.",
        "- `frozen_model.json`: coefficients, scalers, selected penalties, ordered features, and input hashes.",
        "- `../kronos_baseline_v1/`: immutable raw model paths, baseline scores, provenance and reports.",
        "- `../trades_study/`: trade feature files, reconciliation reports and quality gates.", ""]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    # A standalone, readable preview without external dependencies.
    html = ["<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>QQQ study results</title>",
        "<style>body{background:#0b1016;color:#e5edf3;font:15px/1.7 system-ui;margin:40px auto;padding:0 24px;max-width:1100px}h1{color:#84e3bc;font-size:32px}h2{margin-top:36px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #304354;padding:12px;text-align:left}th{color:#96b4ff}p,li{color:#b9c7d3}pre{white-space:pre-wrap}</style>"]
    in_table = False
    for line in lines:
        if line.startswith("|---"):
            continue
        if line.startswith("|"):
            if not in_table:
                html.append("<table>")
                tag = "th"
                in_table = True
            else:
                tag = "td"
            html.append("<tr>" + "".join(f"<{tag}>{escape(c.strip())}</{tag}>" for c in line.strip("|").split("|")) + "</tr>")
            continue
        if in_table:
            html.append("</table>")
            in_table = False
        safe = escape(line.replace("**", "").replace("`", ""))
        if line.startswith("# "):
            html.append(f"<h1>{safe[2:]}</h1>")
        elif line.startswith("## "):
            html.append(f"<h2>{safe[3:]}</h2>")
        elif line.startswith("- "):
            html.append(f"<p>• {safe[2:]}</p>")
        elif line:
            html.append(f"<p>{safe}</p>")
    html.append("</html>")
    (OUT / "report.html").write_text("\n".join(html), encoding="utf-8")
    print(OUT / "RESULTS.md")


if __name__ == "__main__":
    render()
