"""Past-only audited VWAP and minute SMA for frozen zone studies."""
import numpy as np
import pandas as pd


def levels(frame, grid, opening, cutoff):
    cutoff = pd.Timestamp(cutoff)
    past = grid[grid + pd.Timedelta(minutes=1) <= cutoff]
    indexed = frame if frame.index.name == 'bar_start' else frame.set_index('bar_start')
    if indexed.index.duplicated().any():
        raise ValueError('Duplicate input minutes')

    def valid(times):
        rows = indexed.reindex(times)
        good = (len(rows) > 0 and rows.feature_eligible.fillna(False).all()
                and rows.reconciled.fillna(False).all()
                and (rows.available_at <= cutoff).all()
                and np.isfinite(rows[['close', 'volume', 'vwap_close_bps']]).all().all()
                and (rows.volume > 0).all())
        return rows if good else None

    sma = valid(past[-200:]) if len(past) >= 200 else None
    session = valid(past[past >= opening])
    vwap = None
    if session is not None:
        prices = session.close * (1 + session.vwap_close_bps / 10000)
        vwap = float((prices * session.volume).sum() / session.volume.sum())
    return {'Session VWAP': vwap,
            '1m SMA 200': float(sma.close.mean()) if sma is not None else None}
