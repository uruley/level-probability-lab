from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from level_probability_lab.exceptions import ForecastLocked
from level_probability_lab.paths import ensure_dir


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


class ForecastStore:
    """Append-only JSONL store. Existing forecast IDs cannot be rewritten."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._rows: list[dict] = []
        self._ids: set[str] = set()
        if self.path is not None and self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    self._rows.append(row)
                    self._ids.add(row["forecast_id"])

    def put(self, row: dict) -> None:
        fid = row["forecast_id"]
        if fid in self._ids:
            raise ForecastLocked(f"forecast {fid!r} is immutable once stored")
        payload = json.loads(json.dumps(row, default=_json_default))
        self._ids.add(fid)
        self._rows.append(payload)
        if self.path is not None:
            ensure_dir(self.path.parent)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, default=_json_default))
                handle.write("\n")

    def all(self) -> list[dict]:
        return list(self._rows)

    def get(self, forecast_id: str) -> dict:
        for row in self._rows:
            if row["forecast_id"] == forecast_id:
                return row
        raise KeyError(forecast_id)
