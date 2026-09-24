"""Offline QQQ five-minute truth set. No model, network, or live-service calls."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .calendar import session_schedule
from .ghost_candles.storage import ForecastStore

SPEC = 'close_return_pm_10bp_v1'
FIELDS = ('open', 'high', 'low', 'close', 'volume')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utc(value):
    t = pd.Timestamp(value)
    if pd.isna(t) or t.tzinfo is None:
        raise ValueError('Timezone-aware timestamps required')
    return t.tz_convert('UTC')


def validate_bar(row):
    start, end, available = (utc(row[k]) for k in ('bar_start', 'bar_end', 'available_at'))
    if end != start + pd.Timedelta(minutes=1) or available < end:
        raise ValueError('Partial bar or invalid availability')
    values = {k: Decimal(str(row[k])) for k in FIELDS}
    if any(not v.is_finite() or v <= 0 for v in values.values()):
        raise ValueError('Invalid OHLCV')
    if values['high'] < max(values[k] for k in ('open', 'low', 'close')) or values['low'] > min(values[k] for k in ('open', 'close')):
        raise ValueError('Invalid OHLC bounds')
    if row.get('symbol') != 'QQQ' or not row.get('source_id'):
        raise ValueError('QQQ and source_id required')
    return dict(symbol='QQQ', source_id=str(row['source_id']),
                bar_start=start.isoformat(), bar_end=end.isoformat(), available_at=available.isoformat(),
                corrected=bool(row.get('corrected', False)),
                **{k: str(v) for k, v in values.items()})


def snapshot(bars, origin, cutoff, *, experiment_id, source, price_policy,
             availability_policy, code_version, lookback=1):
    """Freeze an exact same-session minute window using only timely records."""
    origin, cutoff = utc(origin), utc(cutoff)
    if not all((experiment_id, source, price_policy, availability_policy, code_version)) or lookback < 1:
        raise ValueError('Explicit provenance and positive lookback required')
    # A forecast made after its first target closes is not a fresh five-minute forecast.
    if not origin <= cutoff < origin + pd.Timedelta(minutes=1):
        raise ValueError('Decision cutoff must precede first target completion')
    day = origin.tz_convert('America/New_York').date()
    schedule = session_schedule(str(day), str(day))
    if schedule.empty:
        raise ValueError('Not an RTH session')
    opening, closing = schedule.iloc[0][['market_open', 'market_close']]
    if origin.floor('min') != origin or origin - pd.Timedelta(minutes=lookback) < opening or origin + pd.Timedelta(minutes=5) > closing:
        raise ValueError('Input or horizon crosses session boundary')
    expected = pd.date_range(origin-pd.Timedelta(minutes=lookback), periods=lookback, freq='min')
    selected = []
    for stamp in expected:
        candidates = [r for r in bars if utc(r['bar_start']) == stamp and utc(r['available_at']) <= cutoff]
        if len(candidates) != 1:
            raise ValueError('Missing, delayed, duplicate or revised input')
        row = validate_bar(candidates[0])
        if row['corrected']:
            raise ValueError('Corrected input is ineligible in v1')
        selected.append(row)
    payload = dict(schema_version='qqq_truth_snapshot_v1', label_spec=SPEC, symbol='QQQ',
                   origin_utc=origin.isoformat(), decision_cutoff_utc=cutoff.isoformat(),
                   horizon_bars=5, threshold='0.001', calendar='NYSE', timezone='UTC',
                   session_open=opening.isoformat(), session_close=closing.isoformat(),
                   experiment_id=experiment_id, source=source, price_policy=price_policy,
                   availability_policy=availability_policy, code_version=code_version,
                   origin_close=selected[-1]['close'], inputs=selected,
                   source_ids=[r['source_id'] for r in selected])
    return dict(payload, snapshot_id=digest(payload))


def score(frozen, bars, as_of):
    """Score exact future minutes; corrections are unscorable, never neutral."""
    payload = {k:v for k,v in frozen.items() if k != 'snapshot_id'}
    if digest(payload) != frozen['snapshot_id'] or frozen['label_spec'] != SPEC:
        raise ValueError('Snapshot integrity or specification mismatch')
    origin, now = utc(frozen['origin_utc']), utc(as_of)
    if now < utc(frozen['decision_cutoff_utc']):
        raise ValueError('Scoring precedes decision')
    expected = pd.date_range(origin, periods=5, freq='min')
    rows, reasons = [], []
    # Check the frozen origin for a subsequently visible correction as well.
    origin_rows = [r for r in bars if utc(r['bar_start']) == origin-pd.Timedelta(minutes=1) and utc(r['available_at']) <= now]
    for r in origin_rows:
        try:
            if validate_bar(r) != frozen['inputs'][-1]: reasons.append('corrected_origin')
        except (ValueError, ArithmeticError): reasons.append('invalid_origin')
    matured = now >= origin + pd.Timedelta(minutes=5)
    if matured:
        for stamp in expected:
            matches = [r for r in bars if utc(r['bar_start']) == stamp and utc(r['available_at']) <= now]
            if len(matches) != 1:
                reasons.append('missing_or_delayed' if not matches else 'duplicate_or_corrected')
                continue
            try:
                row = validate_bar(matches[0])
                if row['corrected']: reasons.append('corrected_future')
                rows.append(row)
            except (ValueError, ArithmeticError): reasons.append('invalid_future')
    status = 'pending' if not matured else 'unscorable' if reasons else 'complete'
    p0 = Decimal(frozen['origin_close'])
    p5 = Decimal(rows[-1]['close']) if status == 'complete' else None
    label = None
    if p5 is not None:
        # Multiplication preserves the exact +/-10bp boundaries without float rounding.
        label = 'bull' if p5 > p0*Decimal('1.001') else 'bear' if p5 < p0*Decimal('0.999') else 'neutral'
    result = dict(snapshot_id=frozen['snapshot_id'], label_spec=SPEC, scored_at=now.isoformat(),
                  status=status, reasons=sorted(set(reasons)), p0=str(p0), p5=str(p5) if p5 is not None else None,
                  return_value=str(p5/p0-1) if p5 is not None else None, label=label,
                  future_bars=rows, expected_starts=[t.isoformat() for t in expected])
    return dict(result, outcome_id=digest(result))


def persist(directory, frozen, outcome):
    """Idempotent content-addressed writes via the existing single-writer store."""
    if outcome['snapshot_id'] != frozen['snapshot_id']:
        raise ValueError('Outcome belongs to another snapshot')
    for name, row, key in [('snapshots', frozen, 'snapshot_id'), ('outcomes', outcome, 'outcome_id')]:
        if digest({k:v for k,v in row.items() if k != key}) != row[key]:
            raise ValueError('Record integrity mismatch')
    for name, row, key in [('snapshots', frozen, 'snapshot_id'), ('outcomes', outcome, 'outcome_id')]:
        store = ForecastStore(Path(directory)/f'{name}.jsonl')
        record = dict(row, forecast_id=row[key])
        try:
            previous = store.get(row[key])
        except KeyError:
            store.put(record)
        else:
            if canonical(previous) != canonical(record): raise ValueError('Immutable record conflict')


def replay(bars, origins, *, as_of, output=None, **metadata):
    """Explicit origins only; caller supplies availability and provenance contracts."""
    results = []
    for origin, cutoff in origins:
        frozen = snapshot(bars, origin, cutoff, **metadata)
        outcome = score(frozen, bars, as_of)
        if output is not None: persist(output, frozen, outcome)
        results.append((frozen, outcome))
    return results
