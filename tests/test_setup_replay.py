from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from level_probability_lab.exceptions import LabError
from level_probability_lab.labeling import build_labels
from level_probability_lab.setup_replay import (
    build_setup_replay_payload,
    run_setup_replay,
    write_setup_replay_html,
)
from tests.conftest import make_cfg, make_session_frame


def _labeled_session():
    n = 40
    closes = [100.0 + 0.05 * np.sin(i / 2) for i in range(n)]
    highs = [c + 1e-6 for c in closes]
    lows = [c - 1e-6 for c in closes]
    highs[22] = closes[20] + 10.0
    bars = make_session_frame(
        n=n,
        closes=closes,
        highs=highs,
        lows=lows,
        session_close="2024-07-01 15:10:00",
    )
    labels = build_labels(bars, make_cfg().get)
    return bars, labels


def test_payload_keeps_frozen_bounds_and_session_key():
    bars, labels = _labeled_session()
    payload = build_setup_replay_payload(bars, labels)
    assert payload["symbol"] == "QQQ"
    assert payload["horizon_minutes"] == 15
    assert len(payload["sessions"]) == 1
    session = payload["sessions"][0]
    assert session["date"] == "2024-07-01"
    assert len(session["bars"]) == 40
    labeled = labels[labels["label"] == "upper_first"].iloc[0]
    match = next(s for s in session["setups"] if s["t"].startswith(str(labeled["prediction_bar_start"])[:19].replace(" ", "T")))
    assert match["label"] == "upper_first"
    assert match["up"] == pytest.approx(float(labeled["upper"]))
    assert match["lo"] == pytest.approx(float(labeled["lower"]))
    assert match["up"] > match["ref"] > match["lo"]


def test_html_embeds_payload_without_script_breakout(tmp_path: Path):
    bars, labels = _labeled_session()
    payload = build_setup_replay_payload(bars, labels)
    path = write_setup_replay_html(tmp_path / "setup_replay.html", payload)
    text = path.read_text(encoding="utf-8")
    assert "Play horizon" in text
    assert "frozen upper / lower" in text
    assert '"date":"2024-07-01"' in text
    assert "</script>" in text
    assert text.count("const DATA = ") == 1


def test_missing_files_raise_lab_error(tmp_path: Path):
    with pytest.raises(LabError, match="labels parquet not found"):
        run_setup_replay(
            labels_path=tmp_path / "missing-labels.parquet",
            bars_path=tmp_path / "missing-bars.parquet",
            out_path=tmp_path / "out.html",
            root=tmp_path,
        )
