from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from level_probability_lab.exceptions import ConfigError
from level_probability_lab.paths import project_root


@dataclass
class Config:
    raw: dict[str, Any]
    path: Path | None
    project_root: Path

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def require(self, *keys: str) -> Any:
        value = self.get(*keys, default=None)
        if value is None:
            raise ConfigError(f"Missing config key: {'.'.join(keys)}")
        return value


def load_config(path: str | Path | None = None, root: Path | None = None) -> Config:
    root = Path(root) if root is not None else project_root()
    if path is None:
        path = root / "configs" / "default.yaml"
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a mapping: {path}")
    return Config(raw=raw, path=path, project_root=root)


def databento_request_from_config(cfg: Config) -> dict[str, Any]:
    symbols = cfg.require("databento", "symbols")
    if isinstance(symbols, str):
        symbol_list = [symbols]
    else:
        symbol_list = [str(s) for s in symbols]
    return {
        "dataset": str(cfg.require("databento", "dataset")),
        "schema": str(cfg.require("databento", "schema")),
        "symbols": sorted(symbol_list),
        "stype_in": str(cfg.get("databento", "stype_in", default="raw_symbol")),
        "start": str(cfg.require("databento", "start")),
        "end": str(cfg.require("databento", "end")),
    }
