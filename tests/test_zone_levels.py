import pandas as pd
import pytest
from level_probability_lab.zone_levels import levels


def test_levels_are_past_only_and_volume_weighted():
    grid = pd.date_range('2026-06-01T13:30Z', periods=202, freq='min')
    frame = pd.DataFrame(dict(bar_start=grid, available_at=grid+pd.Timedelta(minutes=1),
        close=[100.]*199+[102.,999.,999.], volume=[1.]*199+[3.,10000.,10000.],
        vwap_close_bps=0., feature_eligible=True, reconciled=True))
    result = levels(frame,grid,grid[0],grid[200])
    assert result['1m SMA 200'] == pytest.approx(100.01)
    assert result['Session VWAP'] == pytest.approx((19900+306)/202)
    frame.loc[10,'feature_eligible'] = False
    assert levels(frame,grid,grid[0],grid[200]) == {'Session VWAP':None,'1m SMA 200':None}


def test_sma_carries_sessions_but_vwap_resets_and_gaps_are_not_skipped():
    prior = pd.date_range('2026-05-29T18:20Z',periods=100,freq='min')
    today = pd.date_range('2026-06-01T13:30Z',periods=100,freq='min')
    grid=prior.append(today)
    frame=pd.DataFrame(dict(bar_start=grid,available_at=grid+pd.Timedelta(minutes=1),
        close=[100.]*100+[200.]*100,volume=1.,vwap_close_bps=0.,feature_eligible=True,reconciled=True))
    cutoff=grid[-1]+pd.Timedelta(minutes=1)
    assert levels(frame,grid,today[0],cutoff)=={'Session VWAP':200.,'1m SMA 200':150.}
    assert levels(frame.drop(index=0),grid,today[0],cutoff)=={'Session VWAP':200.,'1m SMA 200':None}
