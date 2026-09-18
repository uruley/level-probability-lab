from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from level_probability_lab.paths import ensure_dir


def append_ledger(path: Path, record: dict[str, Any]) -> None:
    """Append-only JSONL. Existing lines are never rewritten."""
    ensure_dir(path.parent)
    payload = dict(record)
    payload.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str))
        handle.write("\n")


def write_leaderboard(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, indent=2, default=str) + "\n", encoding="utf-8")
