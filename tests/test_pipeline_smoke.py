from __future__ import annotations

from level_probability_lab.config import load_config
from level_probability_lab.pipeline import run_smoke
from level_probability_lab.summary import SYNTHETIC_BANNER


def test_offline_smoke_pipeline(tmp_path, project_root):
    cfg = load_config(project_root / "configs" / "smoke.yaml", root=project_root)
    cfg.project_root = tmp_path
    result = run_smoke(cfg)
    assert result["banner"] == SYNTHETIC_BANNER
    assert result["validation_ok"] is True
    assert result["n_labels"] > 0
    summary = result["summary"]
    assert summary["is_synthetic"] is True
    assert "not market evidence" in summary["disclaimer"].lower()
    assert summary["incomplete_and_ambiguous_are_not_neither"] is True
    counts = summary["counts"]
    assert counts["incomplete"] >= 1
    # Planted events plus random path should produce at least one valid class or quality status.
    assert sum(counts.values()) == summary["n_rows"]
    out = tmp_path / "data" / "smoke"
    assert (out / "normalized.parquet").exists()
    assert (out / "labels.parquet").exists()
    assert (out / "summary.json").exists()
