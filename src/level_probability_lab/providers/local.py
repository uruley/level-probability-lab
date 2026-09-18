from __future__ import annotations

from pathlib import Path

import pandas as pd

from level_probability_lab.storage import read_parquet


def load_local_ohlcv(path: Path) -> pd.DataFrame:
    return read_parquet(path)
