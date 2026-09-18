from __future__ import annotations

from pathlib import Path

import pandas as pd

from level_probability_lab.calendar import annotate_session_flags, session_schedule
from level_probability_lab.normalize import raw_to_observed


PILOT_PARQUET = Path(r"C:\Users\ruley\AiStcockProbabilitydoctor\data\raw\XNAS_ITCH_9e345ac44708.ohlcv-1m.parquet")
HISTORY_PARQUET = Path(r"C:\Users\ruley\AiStcockProbabilitydoctor\data\raw\XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet")


def discover_qqq_parquet(root: Path) -> Path:
    raw_dir = root / "data" / "raw"
    preferred = [
        raw_dir / "XNAS_ITCH_9e345ac44708.ohlcv-1m.parquet",
        raw_dir / "XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet",
    ]
    for path in preferred:
        if path.exists():
            return path
    matches = sorted(raw_dir.glob("*.ohlcv-1m.parquet"))
    if not matches:
        raise FileNotFoundError(f"no local OHLCV parquet under {raw_dir}")
    return matches[0]


def load_qqq_session(parquet_path: Path, session_date: str) -> pd.DataFrame:
    raw = pd.read_parquet(parquet_path)
    if "symbol" not in raw.columns:
        raise ValueError(f"{parquet_path} has no symbol column")
    qqq = raw.loc[raw["symbol"].astype(str) == "QQQ"].copy()
    if qqq.empty:
        raise ValueError(f"no QQQ rows in {parquet_path}")
    observed = raw_to_observed(
        qqq,
        interval_minutes=1,
        publication_lag_seconds=0,
        source_dataset="XNAS.ITCH",
        source_schema="ohlcv-1m",
        is_synthetic=False,
    )
    schedule = session_schedule(observed["bar_start"].min(), observed["bar_start"].max())
    flagged = annotate_session_flags(observed, schedule)
    day = pd.Timestamp(session_date).tz_localize(None).normalize()
    session = flagged.loc[
        (flagged["is_regular_session"])
        & (flagged["session_date"] == day)
        & (flagged["bar_status"] == "observed")
    ].sort_values("bar_start")
    if session.empty:
        available = sorted({str(d.date()) for d in flagged["session_date"].dropna().unique()})
        raise ValueError(f"no regular-session QQQ bars for {session_date}; have {available[:12]}")
    return session.reset_index(drop=True)


def list_complete_qqq_sessions(parquet_path: Path, expected_minutes: int = 390) -> list[str]:
    raw = pd.read_parquet(parquet_path)
    qqq = raw.loc[raw["symbol"].astype(str) == "QQQ"].copy()
    observed = raw_to_observed(
        qqq,
        interval_minutes=1,
        publication_lag_seconds=0,
        source_dataset="XNAS.ITCH",
        source_schema="ohlcv-1m",
        is_synthetic=False,
    )
    schedule = session_schedule(observed["bar_start"].min(), observed["bar_start"].max())
    flagged = annotate_session_flags(observed, schedule)
    regular = flagged.loc[(flagged["is_regular_session"]) & (flagged["bar_status"] == "observed")]
    counts = regular.groupby(regular["session_date"]).size()
    complete = counts[counts == expected_minutes]
    return [pd.Timestamp(d).date().isoformat() for d in complete.index]


def load_regular_qqq(parquet_path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(parquet_path)
    qqq = raw.loc[raw["symbol"].astype(str) == "QQQ"].copy()
    observed = raw_to_observed(
        qqq,
        interval_minutes=1,
        publication_lag_seconds=0,
        source_dataset="XNAS.ITCH",
        source_schema="ohlcv-1m",
        is_synthetic=False,
    )
    schedule = session_schedule(observed["bar_start"].min(), observed["bar_start"].max())
    flagged = annotate_session_flags(observed, schedule)
    out = flagged.loc[(flagged["is_regular_session"]) & (flagged["bar_status"] == "observed")]
    return out.sort_values("bar_start").reset_index(drop=True)
