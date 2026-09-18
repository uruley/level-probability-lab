from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from level_probability_lab.exceptions import ValidationError

REQUIRED_COLUMNS = [
    "symbol",
    "bar_start",
    "bar_end",
    "usable_at",
    "bar_status",
]


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            raise ValidationError("; ".join(self.errors))


def validate_normalized(frame: pd.DataFrame) -> ValidationReport:
    report = ValidationReport()
    if frame.empty:
        report.errors.append("normalized frame is empty")
        return report

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        report.errors.append(f"missing columns: {missing}")
        return report

    work = frame.copy()
    work["bar_start"] = pd.to_datetime(work["bar_start"], utc=True)
    work["bar_end"] = pd.to_datetime(work["bar_end"], utc=True)
    work["usable_at"] = pd.to_datetime(work["usable_at"], utc=True)

    if work["bar_start"].dt.tz is None:
        report.errors.append("bar_start is not timezone-aware UTC")

    dup = work.duplicated(subset=["symbol", "bar_start"]).sum()
    if dup:
        report.errors.append(f"duplicate symbol/bar_start rows: {int(dup)}")

    for symbol, grp in work.groupby("symbol", sort=False):
        if not grp["bar_start"].is_monotonic_increasing:
            report.errors.append(f"{symbol}: bar_start is not sorted")

    observed = work[work["bar_status"] == "observed"]
    report.stats["n_rows"] = int(len(work))
    report.stats["n_observed"] = int(len(observed))
    report.stats["n_no_trade"] = int((work["bar_status"] == "no_trade").sum())
    report.stats["n_coverage_gap"] = int((work["bar_status"] == "coverage_gap").sum())
    report.stats["symbols"] = sorted(work["symbol"].astype(str).unique().tolist())

    if not observed.empty:
        ohlc_ok = (
            (observed["low"] <= observed["open"])
            & (observed["low"] <= observed["close"])
            & (observed["low"] <= observed["high"])
            & (observed["high"] >= observed["open"])
            & (observed["high"] >= observed["close"])
        )
        bad_ohlc = int((~ohlc_ok).sum())
        if bad_ohlc:
            report.errors.append(f"OHLC inconsistency on {bad_ohlc} observed bars")

        if (observed["volume"] < 0).any():
            report.errors.append("negative volume on observed bars")

        if observed[["open", "high", "low", "close"]].isna().any().any():
            report.errors.append("NaN OHLC on observed bars")

    unknown_status = sorted(set(work["bar_status"].unique()) - {"observed", "no_trade", "coverage_gap"})
    if unknown_status:
        report.errors.append(f"unknown bar_status values: {unknown_status}")

    if (work["usable_at"] < work["bar_end"]).any():
        report.errors.append("usable_at precedes bar_end")

    return report
