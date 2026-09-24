import pandas as pd
from level_probability_lab.zone_response import observe

def bars():
    return pd.DataFrame(dict(bar_start=pd.date_range('2026-05-01T14:00Z',periods=100,freq='min'),
        open=102.,high=102.1,low=101.9,close=102.,volume=100.,trade_count=5,feature_eligible=True,reconciled=True))

def test_no_touch_and_gap_are_distinct():
    b=bars();assert observe(b,b.bar_start[20],100,102,1)['status']=='no_touch'
    assert observe(b.drop(index=22),b.bar_start[20],100,102,1)['status']=='incomplete'

def test_touch_then_rejection_and_volume():
    b=bars();b.loc[20,['open','high','low','close']]=[100.1,100.2,99.9,100.1]
    r=observe(b,b.bar_start[20],100,102,1)
    assert r['status']=='rejection' and r['volume_ratio']==1

def test_touch_bar_order_and_both_barriers_unknown():
    b=bars();b.loc[20,['open','high','low','close']]=[100,101,99,100]
    assert observe(b,b.bar_start[20],100,102,1)['status']=='ambiguous'

def test_frozen_side_continuation():
    b=bars();b.loc[20,['open','high','low','close']]=[100.1,100.2,99.9,100.1]
    b.loc[21,['open','high','low','close']]=[99.8,99.9,99.4,99.5]
    assert observe(b,b.bar_start[20],100,102,1)['status']=='continuation'
