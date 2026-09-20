import numpy as np
import pandas as pd
from level_probability_lab.range_metrics import forecast_range,observed_range


def test_extremes_per_path_not_pointwise_median():
    a=np.tile([100,101,99,100.],(3,5,1))
    for i in range(3):a[i,i,1]=110+i
    p=forecast_range(a,100)
    assert p['high']['median']==111
    assert p['upside']['median']==11
    assert p['low']['median']==99
    assert p['downside']['median']==1
    a[0,0,1]=90
    assert forecast_range(a,100)['excluded_paths']==1


def test_no_future_range_or_premature_score():
    starts=pd.date_range('2026-05-01T15:30Z',periods=5,freq='min')
    b=pd.DataFrame({'bar_start':starts,'bar_end':starts+pd.Timedelta(minutes=1),'high':[101,102,103,104,120],'low':[99,98,97,96,80]})
    p=forecast_range(np.tile([100,105,95,100],(2,5,1)),100)
    first=observed_range(p,starts,b.iloc[:1])
    assert first['actual']['high']==101 and first['status']=='pending'
    assert first['absolute_errors']['high'] is None
    final=observed_range(p,starts,b)
    assert final['status']=='complete' and final['absolute_errors']['high']==15
    gap=observed_range(p,starts,b.drop(index=2))
    assert gap['status']=='incomplete' and gap['absolute_errors']['high'] is None
