import numpy as np
import pandas as pd
from level_probability_lab.touch_experiment import first_touch,setup,observe,summary


def record():
    return {'input_window':[dict(open=100,high=101,low=99,close=100) for _ in range(20)],
            'sampled_paths':np.tile([100,101.5,99.5,101.],(4,5,1)).tolist()}


def test_order_and_ambiguity():
    assert first_touch([[100,103,99,101],[101,101,95,96]],102,98,1)=='target_first'
    assert first_touch([[100,101,97,98],[98,104,97,102]],102,98,1)=='stop_first'
    assert first_touch([[100,103,97,100]],102,98,1)=='ambiguous'
    assert first_touch([[100,101,97,98]],98,102,-1)=='target_first'
    assert first_touch([[100,103,99,102]],98,102,-1)=='stop_first'
    assert first_touch([[100,101,99,100]],102,98,1)=='neither'


def test_atr_levels_neutral_and_missing():
    r=record();s=setup(r)
    assert s['risk']==2 and s['direction']=='up'
    assert [x['target'] for x in s['setups']]==[102,104,106]
    assert {x['stop'] for x in s['setups']}=={98}
    assert all(sum(x['path_percentages'].values())==100 for x in s['setups'])
    stamps=pd.date_range('2026-05-01T15:30Z',periods=5,freq='min')
    b=pd.DataFrame(dict(bar_start=stamps,bar_end=stamps+pd.Timedelta(minutes=1),open=100,high=103,low=99,close=101))
    assert observe(s,stamps,b.iloc[:1])[0]['outcome']=='target_first'
    assert observe(s,stamps,b)[0]['outcome']=='target_first'
    assert observe(s,stamps,b.drop(index=0))[0]['status']=='incomplete'
    result=summary([{'touch_outcomes':observe(s,stamps,b)}])
    assert result[0]['percentages']['target_first']==100
    r['sampled_paths']=np.tile([100,101,99,100],(4,5,1)).tolist()
    assert setup(r)['status']=='neutral'


def test_extended_deadlines_gaps_and_frozen_levels():
    s=setup(record())
    stamps=pd.date_range('2026-05-01T15:30Z',periods=65,freq='min')
    b=pd.DataFrame(dict(bar_start=stamps,bar_end=stamps+pd.Timedelta(minutes=1),
                        open=100,high=101,low=99,close=100,session_close=stamps[64]))
    assert observe(s,stamps[:5],b.iloc[:5])[0]['outcome']=='neither'
    assert observe(s,stamps[:5],b.iloc[:5],True)[0]['status']=='open'
    b.loc[39,'high']=103
    r=observe(s,stamps[:5],b.iloc[:40],True)
    assert r[0]['outcome']=='target_first' and r[0]['minutes_to_resolution']==40
    assert r[1]['status']=='open'
    assert observe(s,stamps[:5],b.drop(index=10),True)[0]['status']=='incomplete'
    assert observe(s,stamps[:5],b,True)[1]['outcome']=='expired'
    b.loc[60,'high']=110
    assert observe(s,stamps[:5],b,True)[1]['outcome']=='expired'
    b['session_close']=stamps[10]
    r=observe(s,stamps[:5],b,True)
    assert r[0]['outcome']=='expired' and r[0]['minutes_to_resolution']==10
    assert summary([{'extended_touch_outcomes':r}],True)[0]['counts']['expired']==1


def test_early_ambiguity_and_missing_after_resolution():
    s=setup(record());stamps=pd.date_range('2026-05-01T15:30Z',periods=5,freq='min')
    b=pd.DataFrame(dict(bar_start=stamps,bar_end=stamps+pd.Timedelta(minutes=1),open=100,high=103,low=97,close=100))
    assert observe(s,stamps,b.iloc[:1])[0]['outcome']=='ambiguous'
    assert observe(s,stamps,b.drop(index=2))[0]['outcome']=='ambiguous'


def test_no_future_candle_is_pending_not_missing():
    s=setup(record());start=pd.Timestamp('2026-05-01T15:30Z')
    b=pd.DataFrame([dict(bar_start=start-pd.Timedelta(minutes=1),bar_end=start,open=100,high=101,low=99,close=100,session_close=start+pd.Timedelta(hours=2))])
    targets=pd.date_range(start,periods=5,freq='min')
    assert observe(s,targets,b)[0]['status']=='pending'
    assert observe(s,targets,b,True)[0]['status']=='open'
