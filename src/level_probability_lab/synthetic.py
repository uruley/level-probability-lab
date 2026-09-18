from __future__ import annotations

import numpy as np
import pandas as pd

from level_probability_lab.calendar import session_minute_index, session_schedule


def _random_ohlc(rng: np.random.Generator, prev_close: float, sigma: float) -> tuple[float, float, float, float, int]:
    ret = rng.normal(0.0, sigma)
    close = max(prev_close * np.exp(ret), 0.01)
    open_ = prev_close
    wick = abs(rng.normal(0.0, sigma * prev_close * 0.25))
    high = max(open_, close) + wick
    low = min(open_, close) - wick
    low = max(low, 0.01)
    volume = int(rng.integers(1000, 9000))
    return float(open_), float(high), float(low), float(close), volume


def _walk_symbol(
    index: pd.DatetimeIndex,
    start_price: float,
    rng: np.random.Generator,
    sigma: float,
    symbol: str,
) -> pd.DataFrame:
    rows = []
    price = start_price
    for ts in index:
        o, h, l, c, v = _random_ohlc(rng, price, sigma)
        rows.append(
            {
                "symbol": symbol,
                "ts_event": ts,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            }
        )
        price = c
    return pd.DataFrame(rows)


def _set_bar(df: pd.DataFrame, ts: pd.Timestamp, **fields) -> None:
    idx = df.index[df["ts_event"] == ts]
    if len(idx) != 1:
        return
    for key, value in fields.items():
        df.loc[idx[0], key] = value


def generate_synthetic_ohlcv(
    *,
    start: str,
    end: str,
    seed: int,
    qqq_start: float,
    spy_start: float,
    sigma: float,
    calendar_name: str = "NYSE",
) -> pd.DataFrame:
    """Deterministic QQQ/SPY-style 1-minute bars. Plumbing test data only."""
    rng = np.random.default_rng(seed)
    schedule = session_schedule(start, end, calendar_name=calendar_name)
    if schedule.empty:
        raise ValueError(f"no NYSE sessions in {start} .. {end}")

    parts_q = []
    parts_s = []
    q_price = qqq_start
    s_price = spy_start
    for row in schedule.itertuples():
        idx = session_minute_index(row.market_open, row.market_close)
        q = _walk_symbol(idx, q_price, rng, sigma, "QQQ")
        s = _walk_symbol(idx, s_price, rng, sigma, "SPY")
        q_price = float(q["close"].iloc[-1])
        s_price = float(s["close"].iloc[-1])
        parts_q.append(q)
        parts_s.append(s)

    qqq = pd.concat(parts_q, ignore_index=True)
    spy = pd.concat(parts_s, ignore_index=True)

    first_open = pd.Timestamp(schedule.iloc[0]["market_open"])
    plant = first_open + pd.Timedelta(minutes=150)
    ref_rows = qqq[qqq["ts_event"] == plant]
    if not ref_rows.empty:
        ref = float(ref_rows["close"].iloc[0])
        # Quiet window so a later neither path is possible around this region.
        quiet = qqq[(qqq["ts_event"] >= plant) & (qqq["ts_event"] < plant + pd.Timedelta(minutes=15))]
        for i in quiet.index:
            px = ref
            qqq.loc[i, ["open", "high", "low", "close"]] = [px, px + 0.01, px - 0.01, px]
            qqq.loc[i, "volume"] = 2000
        _set_bar(
            qqq,
            plant + pd.Timedelta(minutes=20),
            open=ref,
            high=ref + 5.0,
            low=ref - 0.02,
            close=ref + 0.4,
            volume=8000,
        )
        _set_bar(
            qqq,
            plant + pd.Timedelta(minutes=40),
            open=ref,
            high=ref + 0.02,
            low=ref - 5.0,
            close=ref - 0.4,
            volume=8000,
        )
        _set_bar(
            qqq,
            plant + pd.Timedelta(minutes=60),
            open=ref,
            high=ref + 5.0,
            low=ref - 5.0,
            close=ref,
            volume=9000,
        )

    # Coverage gap on the last full session: drop 30 consecutive minutes.
    last_full = None
    for row in schedule.itertuples():
        length = (pd.Timestamp(row.market_close) - pd.Timestamp(row.market_open))
        if length >= pd.Timedelta(hours=6):
            last_full = row
    if last_full is not None:
        gap_start = pd.Timestamp(last_full.market_open) + pd.Timedelta(minutes=180)
        gap_end = gap_start + pd.Timedelta(minutes=30)
        qqq = qqq[~((qqq["ts_event"] >= gap_start) & (qqq["ts_event"] < gap_end))]
        spy = spy[~((spy["ts_event"] >= gap_start) & (spy["ts_event"] < gap_end))]

    out = pd.concat([qqq, spy], ignore_index=True).sort_values(["symbol", "ts_event"]).reset_index(drop=True)
    out["is_synthetic"] = True
    return out
