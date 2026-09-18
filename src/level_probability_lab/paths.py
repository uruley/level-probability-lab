from __future__ import annotations

from pathlib import Path


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return package_dir().parents[1]


def data_dir(root: Path | None = None, data_dirname: str = "data") -> Path:
    return (root or project_root()) / data_dirname


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_data_layout(root: Path | None = None, data_dirname: str = "data") -> dict[str, Path]:
    base = data_dir(root, data_dirname)
    layout = {
        "data": base,
        "raw": base / "raw",
        "normalized": base / "normalized",
        "labels": base / "labels",
        "manifests": base / "manifests",
        "quotes": base / "manifests" / "quotes",
        "downloads": base / "manifests" / "downloads",
        "reports": base / "reports",
        "smoke": base / "smoke",
    }
    for path in layout.values():
        ensure_dir(path)
    return layout
