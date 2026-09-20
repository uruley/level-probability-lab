import json
import numpy as np
import pandas as pd
from level_probability_lab.market_context import aggregate, snapshot, save_context


def fixture():
    ends=pd.date_range('2025-01-01',periods=205,freq='D',tz='UTC')
    frame=pd.DataFrame(dict(end=ends,close=np.arange(205.)+100,high=np.arange(205.)+101,low=np.arange(205.)+99))
    start=ends[-1]+pd.Timedelta(days=1)
    visible=pd.DataFrame(dict(bar_start=[start,start+pd.Timedelta(minutes=1)],bar_end=[start+pd.Timedelta(minutes=1),start+pd.Timedelta(minutes=2)],open=304,high=306,low=303,close=[304,305],session_open=start))
    return {'daily':frame.copy(),'hourly':frame.copy()},visible


def test_formulas_future_invariance_and_persistence(tmp_path):
    h,v=fixture();s=snapshot(h,v,2,'up')
    level=next(x for x in s['levels'] if x['name']=='SMA 5' and x['timeframe']=='daily')
    assert level['value']==302 and level['slope']==1 and level['distance_r']==1.5
    expected=np.std(np.arange(285.,305.),ddof=0)
    upper=next(x for x in s['levels'] if x['name']=='BB upper' and x['timeframe']=='daily')
    assert abs(upper['value']-(294.5+2*expected))<1e-9
    for key in h:
        h[key]=pd.concat([h[key],pd.DataFrame([dict(end=v.iloc[-1].bar_end+pd.Timedelta(hours=1),close=9999,high=9999,low=9999)])])
    assert snapshot(h,v,2,'up')==s
    identity=save_context(s,'forecast',tmp_path)
    assert save_context(s,'forecast',tmp_path)==identity
    assert json.loads((tmp_path/'market_context'/f'{identity}.json').read_text())['context']==s


def test_missing_history_and_confluence():
    h,v=fixture()
    for key in h: h[key]['close']=305
    s=snapshot(h,v,2)
    assert s['location_group']=='confluence' and len(s['confluence_pairs'])==36
    h['daily'].loc[204,'close']=np.nan
    s=snapshot(h,v,2)
    assert s['location_group']=='unknown'
    assert all(x['value'] is None for x in s['levels'] if x['timeframe']=='daily' and x['name'].startswith('SMA'))


def test_session_anchoring_missing_minutes_and_short_tail():
    start=pd.Timestamp('2026-05-01T13:30Z');end=start+pd.Timedelta(minutes=150)
    stamps=pd.date_range(start,end,freq='min',inclusive='left')
    raw=pd.DataFrame(dict(bar_start=stamps,open=100,high=101,low=99,close=np.arange(150.)+100))
    raw['high']=raw.close+1;raw['open']=raw.close
    schedule=pd.DataFrame(dict(market_open=[start],market_close=[end]))
    h=aggregate(raw,schedule)
    assert len(h['hourly'])==2 and h['hourly'].iloc[0].end==start+pd.Timedelta(hours=1)
    assert h['daily'].iloc[0].close==249
    h=aggregate(raw.drop(index=10),schedule)
    assert np.isnan(h['hourly'].iloc[0].close) and np.isnan(h['daily'].iloc[0].close)
    assert h['hourly'].iloc[1].close==219
