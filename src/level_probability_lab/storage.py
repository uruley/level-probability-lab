from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from level_probability_lab.paths import ensure_dir


def write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    ensure_dir(path.parent)
    frame.to_parquet(path, index=False)
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def write_json(payload: Any, path: Path) -> Path:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=_json_default)
        handle.write("\n")
    return path


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
