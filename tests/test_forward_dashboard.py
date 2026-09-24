import pandas as pd
import numpy as np
from level_probability_lab.forward_dashboard import freeze_context,score


def fixture():
    t=pd.date_range('2026-09-23T13:30Z',periods=25,freq='min')
    bars=pd.DataFrame(dict(bar_start=t,bar_end=t+pd.Timedelta(minutes=1),open=100.,high=101.,low=99.,close=100.,volume=10.,session_open=t[0],session_close=pd.Timestamp('2026-09-23T20:00Z')))
    row=dict(forecast_id='test',last_input_timestamp=t[19].isoformat(),forecast_created_at=t[20].isoformat(),target_timestamps=[x.isoformat() for x in t[20:]],model_name='Kronos',input_window=bars.iloc[:20].to_dict('records'),sampled_paths=np.tile([100.,101.,99.,100.5],(2,5,1)).tolist())
    return bars,row


def test_complete_gap_pending_and_baseline():
    bars,row=fixture();now=bars.iloc[-1].bar_end
    r=score(row,bars,now)
    assert r['status']=='complete' and r['close_error']==.5 and r['baseline_error']==0
    assert r['high_error']==r['low_error']==0
    assert score(row,bars.drop(index=22),now)['status']=='incomplete'
    assert score(row,bars.iloc[:22],bars.iloc[21].bar_end)['status']=='pending'
    row['forecast_created_at']=now.isoformat()
    assert not score(row,bars,now)['prospective']


def test_context_never_shortens_average_or_bridges_gap():
    bars,_=fixture();r=freeze_context(bars.iloc[:20])
    assert r['session_vwap_approx']==100 and r['sma200'] is None
    assert freeze_context(bars.iloc[:20].drop(index=3))['session_vwap_approx'] is None
