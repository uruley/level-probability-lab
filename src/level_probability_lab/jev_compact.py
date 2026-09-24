"""Offline, allowlisted summary of an archived Kronos forecast; no outcomes."""
import hashlib
import json
import numpy as np
import pandas as pd


def build_compact(row):
    origin = pd.Timestamp(row['origin'])
    if origin.tzinfo is None or origin.strftime('%Y-%m') not in ('2026-05', '2026-06'):
        raise ValueError('Only timezone-aware May/June development origins allowed')
    paths = np.asarray(row['sampled_ohlc'], dtype=float)
    price = float(row['origin_close'])
    if paths.ndim != 3 or paths.shape[1:] != (5, 4) or len(paths) == 0 or not np.isfinite(paths).all() or not np.isfinite(price) or price <= 0 or (paths <= 0).any():
        raise ValueError('Invalid forecast paths or origin price')
    invalid_ohlc = ((paths[:, :, 1] < paths.max(axis=2)) |
                    (paths[:, :, 2] > paths.min(axis=2))).any(axis=1)
    expected = pd.date_range(origin + pd.Timedelta(minutes=1), periods=5, freq='min')
    if not pd.DatetimeIndex(pd.to_datetime(row['targets'], utc=True)).equals(expected):
        raise ValueError('Targets must be exact subsequent minute grid')
    returns = (paths[:, :, 3] / price - 1) * 10000
    final = returns[:, -1]
    package = dict(schema_version='jev_compact_v1', symbol='QQQ',
        cutoff=(origin + pd.Timedelta(minutes=1)).isoformat(),
        target_final_close=(origin + pd.Timedelta(minutes=6)).isoformat(),
        origin_close=price, label=dict(horizon_minutes=5, bull_gt_bp=10,
        bear_lt_bp=-10, neutral='inclusive [-10,10] bp'),
        kronos=dict(model=row['model'], sample_count=len(paths),
            invalid_ohlc_path_count=int(invalid_ohlc.sum()),
            summary_policy='close-only; finite closes retained regardless of high/low ordering; no range claim',
            close_return_bp_quantiles=dict(zip(('p10', 'p50', 'p90'),
                np.round(np.quantile(returns, [.1, .5, .9], axis=0), 4).tolist())),
            final_class_frequencies=dict(bull=float(np.mean(final > 10)),
                neutral=float(np.mean(abs(final) <= 10)), bear=float(np.mean(final < -10))),
            semantics='raw sampled forecasts; not calibrated'),
        market_context=dict(status='unavailable'), order_flow=dict(status='unavailable'))
    canonical = json.dumps(package, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return package, hashlib.sha256(canonical.encode()).hexdigest()
