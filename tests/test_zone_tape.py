import pandas as pd
from level_probability_lab.zone_tape import resolve

def test_pre_touch_high_does_not_count_as_rejection():
    t=pd.Timestamp('2026-05-01T15:30Z')
    tape=pd.DataFrame(dict(ts_recv=[t,t+pd.Timedelta(seconds=1),t+pd.Timedelta(seconds=2)],price=[101,100,99.4],size=[1,2,3]))
    event=dict(cutoff=t,level=100,risk=1,price=102)
    r=resolve(tape,event,t)
    assert r['status']=='continuation' and r['zone_shares_until_resolution']==2

def test_same_timestamp_cannot_resolve_order():
    t=pd.Timestamp('2026-05-01T15:30Z')
    tape=pd.DataFrame(dict(ts_recv=[t,t],price=[100,101],size=[1,2]))
    assert resolve(tape,dict(cutoff=t,level=100,risk=1,price=102),t)['status']=='ambiguous'
