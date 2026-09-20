import pandas as pd
import pytest
from level_probability_lab.trade_amount import attach_amount


def test_amount_join_blocks_future_missing_and_mismatch(tmp_path):
    window = pd.DataFrame({'bar_start': pd.to_datetime(['2026-05-01T14:00Z']), 'bar_end': pd.to_datetime(['2026-05-01T14:01Z']), 'open': [10.], 'high': [11.], 'low': [9.], 'close': [10.5], 'volume': [100.]})
    rows = window.drop(columns='bar_end').rename(columns={c: 'trade_'+c for c in ['open','high','low','close','volume']})
    rows['available_at'] = window.bar_end
    rows['amount'] = 1020.
    path = tmp_path / 'amounts.parquet'
    rows.to_parquet(path)
    assert attach_amount(window, path).amount.iloc[0] == 1020.
    for field, value in [('available_at', pd.Timestamp('2026-05-01T14:02Z')), ('amount', float('nan')), ('trade_volume', 99.)]:
        bad = rows.copy(); bad[field] = value; bad.to_parquet(path)
        with pytest.raises(ValueError): attach_amount(window, path)
    window['bar_start'] = pd.to_datetime(['2026-07-01T14:00Z'])
    with pytest.raises(ValueError, match='restricted'): attach_amount(window, path)
