import json
import numpy as np
import pandas as pd
from level_probability_lab.chart_data import prepare, payload


def test_history_cutoff_and_rolling_missing():
    start=pd.date_range('2026-01-01',periods=205,freq='D',tz='UTC')
    frame=pd.DataFrame(dict(start=start,end=start+pd.Timedelta(hours=6),open=100.,high=400.,low=90.,close=np.arange(205.)+100,volume=10.))
    ready=prepare({'daily':frame})
    cutoff=frame.iloc[202].end
    rows=payload(ready,cutoff)['daily']
    assert len(rows)==203
    assert rows[-1]['sma200']==202-199/2+100
    assert all(pd.Timestamp(r['end'])<=cutoff for r in rows)
    frame.loc[203:,'close']=99999
    assert payload(prepare({'daily':frame}),cutoff)=={'daily':rows}
    frame.loc[200,'close']=np.nan
    missing=payload(prepare({'daily':frame}),cutoff)['daily']
    assert missing[-1]['sma5'] is None and missing[200]['c'] is None
    json.dumps(missing,allow_nan=False)


def test_exact_completion_boundary():
    start=pd.Timestamp('2026-05-01T13:30Z')
    frame=pd.DataFrame([dict(start=start,end=start+pd.Timedelta(hours=1),open=100.,high=101.,low=99.,close=100.,volume=1.)])
    prepared=prepare({'hourly':frame})
    assert payload(prepared,start+pd.Timedelta(minutes=59))['hourly']==[]
    assert len(payload(prepared,start+pd.Timedelta(minutes=60))['hourly'])==1
