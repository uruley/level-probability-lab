import numpy as np
import pandas as pd
import pytest
from level_probability_lab.companion_features import aggregate_completed, build_features


def bars(day):
    opening=pd.Timestamp(day+' 09:30',tz='America/New_York').tz_convert('UTC')
    start=pd.date_range(opening,periods=390,freq='min')
    c=100+np.arange(390)*.01
    return pd.DataFrame(dict(bar_start=start,bar_end=start+pd.Timedelta(minutes=1),
                            session_open=opening,session_close=opening+pd.Timedelta(minutes=390),
                            open=c,high=c+.1,low=c-.1,close=c,volume=100))


def package(b,n=120):
    window=b.iloc[:n].tail(120)
    records=window[['bar_start','open','high','low','close','volume']].copy()
    records['bar_start']=records.bar_start.map(lambda t:t.isoformat())
    return dict(package_id='test',cutoff=b.iloc[n-1].bar_end.isoformat(),
                kronos_inputs={'candles':records.to_dict('records')},
                forecast={'sampled_paths':np.ones((25,5,4)).tolist()},
                companion_inputs={'trade_minutes':[]})


def test_1037_excludes_forming_bars():
    b=bars('2026-05-01');opening=b.iloc[0].session_open
    cutoff=opening+pd.Timedelta(minutes=67)
    five=aggregate_completed(b,opening,cutoff,5)
    hour=aggregate_completed(b,opening,cutoff,60)
    assert five[-1]['end']==opening+pd.Timedelta(minutes=65)
    assert hour[-1]['end']==opening+pd.Timedelta(minutes=60)
    with pytest.raises(ValueError,match='Ineligible'):build_features(package(b,67),b,bars('2026-04-30'))


def test_formulas_and_future_invariance():
    b=bars('2026-05-01');p=package(b);prev=bars('2026-04-30')
    f=build_features(p,b,prev)
    # Constant 0.2 true range -> Wilder ATR remains 0.2.
    assert f['range_1m_atr']==pytest.approx(1)
    assert f['dist_sma20_atr']==pytest.approx(.095/.2)
    assert f['sma50_slope_atr']==pytest.approx(.1/.2)
    assert f['nasdaq_vol_ratio_20']==1
    assert not f['ts_block_available'] and np.isnan(f['ts_n_1m'])
    b.loc[120:,['close','high','low','volume']]=999999
    newer=build_features(p,b,prev)
    for key,value in f.items():
        if isinstance(value,float) and np.isnan(value):assert np.isnan(newer[key])
        else:assert newer[key]==value


def test_gap_and_close_rejection():
    b=bars('2026-05-01');prev=bars('2026-04-30')
    with pytest.raises(ValueError,match='complete session'):build_features(package(b),b.drop(index=20),prev)
    with pytest.raises(ValueError,match='Ineligible'):build_features(package(b,386),b,prev)
    b['session_close']=b.iloc[0].session_open+pd.Timedelta(minutes=210)
    with pytest.raises(ValueError,match='Ineligible'):build_features(package(b,206),b,prev)
