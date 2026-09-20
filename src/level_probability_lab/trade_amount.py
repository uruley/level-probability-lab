"""Local May/June trade-dollar input experiment. No acquisition or July scoring."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def attach_amount(window, path):
    if not window.bar_start.dt.strftime('%Y-%m').isin(['2026-05', '2026-06']).all():
        raise ValueError('Actual trade totals are restricted to May–June 2026 development sessions.')
    amounts = pd.read_parquet(path)
    joined = window.merge(amounts, on='bar_start', how='left', validate='one_to_one')
    if (joined.amount.isna().any() or not np.isfinite(joined.amount).all()
            or (joined.amount <= 0).any()
            or joined.available_at.isna().any()
            or (joined.available_at > joined.bar_end).any()):
        raise ValueError('Missing, invalid, or unavailable trade totals; no approximation fallback.')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if not np.isclose(joined[col], joined['trade_' + col], rtol=0, atol=1e-7 if col != 'volume' else 0).all():
            raise ValueError('Trade totals do not reconcile with the replay candles.')
    return joined[ list(window.columns) + ['amount'] ]


def build(root):
    import databento as db
    raw = root / 'data/raw/XNAS_ITCH_81b52cd2b2a9.trades.dbn.zst'
    feature_path = root / 'data/trades_study/trade_features_may_june.parquet'
    audit = json.loads((root / 'data/trades_study/trade_feature_audit.json').read_text())
    for path, key in [(raw, 'raw_sha256'), (feature_path, 'features_sha256')]:
        if hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != audit[key]:
            raise ValueError('Input hash differs from accepted trade audit')
    if not audit['accepted']:
        raise ValueError('Trade audit not accepted')
    features = pd.read_parquet(feature_path)
    eligible = features.loc[features.feature_eligible & features.reconciled].copy()
    parts = []
    for chunk in db.DBNStore.from_file(raw).to_df(price_type='float', pretty_ts=True, count=250000):
        stamp = chunk.index if chunk.index.name == 'ts_recv' else pd.to_datetime(chunk.ts_recv, utc=True)
        take = (stamp >= pd.Timestamp('2026-05-01', tz='UTC')) & (stamp < pd.Timestamp('2026-07-01', tz='UTC'))
        selected = chunk.loc[take].copy()
        if selected.empty:
            continue
        selected['bar_start'] = stamp[take].floor('min')
        selected = selected.loc[selected.bar_start.isin(eligible.bar_start)]
        if not (selected.symbol == 'QQQ').all():
            raise ValueError('Unexpected symbol')
        selected['amount'] = selected.price.astype(float) * selected['size'].astype(float)
        parts.append(selected.groupby('bar_start').amount.sum())
    totals = pd.concat(parts).groupby(level=0).sum().rename('amount').reset_index()
    result = eligible[['bar_start', 'available_at', 'open', 'high', 'low', 'close', 'volume']].merge(totals, validate='one_to_one')
    if len(result) != len(eligible) or not np.isfinite(result.amount).all() or (result.amount <= 0).any():
        raise ValueError('Incomplete dollar totals')
    result = result.rename(columns={c: 'trade_' + c for c in ['open', 'high', 'low', 'close', 'volume']})
    output = root / 'data/trade_amount_v1'
    output.mkdir(exist_ok=True)
    result.to_parquet(output / 'amounts.parquet', index=False)
    (output / 'provenance.json').write_text(json.dumps({'raw_sha256': audit['raw_sha256'], 'features_sha256': audit['features_sha256'], 'rows': len(result), 'definition': 'sum(price * size), grouped by receive-time minute', 'months': ['2026-05', '2026-06']}, indent=2))
    print(f'Prepared {len(result)} validated development minutes')


if __name__ == '__main__':
    from .paths import project_root
    build(project_root())
