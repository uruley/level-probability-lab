"""Versioned, past-only evidence records for the replay companion pipeline."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .trade_features import FEATURES


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def build_package(forecast, trades=None, provenance=None):
    candles = [dict(row) for row in forecast['input_window']]
    starts = pd.to_datetime([r['bar_start'] for r in candles], utc=True)
    origin = pd.Timestamp(forecast['last_input_timestamp'])
    cutoff = origin + pd.Timedelta(minutes=1)
    if not len(starts) or starts[-1] != origin or starts.has_duplicates or not starts.is_monotonic_increasing:
        raise ValueError('Invalid forecast input timestamps')
    if len(starts) > 1 and not (starts[1:] - starts[:-1] == pd.Timedelta(minutes=1)).all():
        raise ValueError('Noncontiguous forecast inputs')
    targets = pd.to_datetime(forecast['target_timestamps'], utc=True)
    if list(targets) != list(pd.date_range(cutoff, periods=5, freq='min')):
        raise ValueError('Expected five elapsed-minute targets')
    for row in candles:
        row.setdefault('amount', float(row['volume']) * float(row['close']))
    records = []
    status = 'unavailable'
    if trades is not None:
        selected = trades.loc[trades.bar_start.isin(starts)].copy()
        if selected.bar_start.duplicated().any():
            raise ValueError('Duplicate trade minutes')
        for stamp in starts:
            match = selected.loc[selected.bar_start == stamp]
            if match.empty:
                records.append({'bar_start': stamp.isoformat(), 'status': 'missing', 'features': None})
                continue
            r = match.iloc[0]
            timely = (pd.notna(r.available_at) and pd.notna(r.last_received_at)
                      and r.available_at <= stamp + pd.Timedelta(minutes=1)
                      and r.available_at <= cutoff and r.last_received_at < r.available_at)
            eligible = bool(r.feature_eligible == True and r.reconciled == True)
            candle = candles[list(starts).index(stamp)]
            matched = all(np.isclose(float(r[c]), candle[c], rtol=0, atol=1e-7 if c != 'volume' else 0)
                          for c in ['open', 'high', 'low', 'close', 'volume'])
            valid = timely and eligible and matched and np.isfinite(r[FEATURES].to_numpy(dtype=float)).all()
            records.append({'bar_start': stamp.isoformat(), 'status': 'valid' if valid else 'ineligible',
                            'available_at': r.available_at.isoformat() if pd.notna(r.available_at) else None,
                            'features': {c: float(r[c]) for c in FEATURES} if valid else None})
        status = 'complete' if all(r['status'] == 'valid' for r in records) else 'incomplete'
    payload = {'schema_version': 1, 'forecast_id': forecast['forecast_id'],
               'cutoff': cutoff.isoformat(), 'timezone': 'UTC', 'feed': 'XNAS.ITCH / Nasdaq only',
               'availability_assumption': 'Candles available at bar end; trade summaries use receive-time minutes.',
               'kronos_inputs': {'amount_mode': forecast.get('amount_mode', 'approximate'), 'candles': candles},
               'companion_inputs': {'trade_status': status, 'trade_minutes': records},
               'forecast': {k: forecast[k] for k in ['model_name', 'model_revision', 'random_seed',
                            'sample_count', 'target_timestamps', 'sampled_paths']},
               'provenance': provenance or {}}
    payload['package_id'] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    return payload


def save_package(forecast, root, output):
    """Called under the lab store lock. Never reads July trade features."""
    month = pd.Timestamp(forecast['last_input_timestamp']).strftime('%Y-%m')
    trades, provenance = None, {'candle_source': forecast.get('source'), 'assembly': 'from frozen forecast inputs'}
    if month in ('2026-05', '2026-06'):
        path = root / 'data/trades_study/trade_features_may_june.parquet'
        audit_path = root / 'data/trades_study/trade_feature_audit.json'
        if path.exists() and audit_path.exists():
            audit = json.loads(audit_path.read_text())
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if not audit['accepted'] or digest != audit['features_sha256']:
                raise ValueError('Trade feature audit mismatch')
            trades = pd.read_parquet(path)
            provenance.update(trade_features_sha256=digest, raw_trades_sha256=audit['raw_sha256'])
    package = build_package(forecast, trades, provenance)
    directory = Path(output) / 'input_packages'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (package['package_id'] + '.json')
    text = canonical(package)
    if path.exists():
        if path.read_text(encoding='utf-8') != text:
            raise ValueError('Existing input package differs')
    else:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(text)
    return package['package_id']


def save_outcomes(state, output):
    """Separate immutable snapshots containing only outcomes revealed so far."""
    for forecast in state['forecasts']:
        row = {'forecast_id': forecast.get('id'), 'package_id': forecast.get('input_package_id'), 'revealed_through': state['clock'],
               'targets': forecast['targets'], 'actual_close': forecast['actual'],
               'status': forecast['outcome_status'],
               'range_forecast': forecast.get('range_forecast'),
               'range_outcome': forecast.get('range_outcome'),
               'market_context_id': forecast.get('market_context_id'),
               'touch_setup': forecast.get('touch_setup'),
               'touch_outcomes': forecast.get('touch_outcomes'),
               'extended_touch_outcomes': forecast.get('extended_touch_outcomes')}
        text = canonical(row)
        identity = hashlib.sha256(text.encode()).hexdigest()
        directory = Path(output) / 'outcomes'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (identity + '.json')
        if not path.exists():
            with path.open('x', encoding='utf-8') as stream:
                stream.write(text)
