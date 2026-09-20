import numpy as np
import pandas as pd
from level_probability_lab.location_evaluation import score_path, interval, contrast


def test_touch_order_deadline_missing_and_neutral():
    path=np.array([[100,101,99,100],[100,103,99,102],[102,103,97,98.]])
    assert score_path(path,100,2,1,1,3)['outcome']=='target_first'
    assert score_path(path,100,2,-1,1,3)['outcome']=='stop_first'
    assert score_path(path,100,2,1,1,1)['outcome']=='neither'
    assert score_path(path,100,2,0,1,3)['status']=='no_setup'
    path[0]=np.nan
    assert score_path(path,100,2,1,1,3)['status']=='incomplete'
    assert score_path(np.array([[100,103,97,100]]),100,2,1,1,1)['outcome']=='ambiguous'


def test_session_bootstrap_pairing_and_sparse_groups():
    f=pd.DataFrame(dict(date=['a','a','b','b'],group=['confluence','no_confluence']*2,n=[1,0,1,0],d=[1,1,1,1]))
    assert contrast(f,'n','d')['ci95']==[1.,1.]
    assert interval(f,'n','d')['value']==.5
    assert interval(f.iloc[:2],'n','d')['ci95'] is None
    assert contrast(f.loc[f.group=='confluence'],'n','d')['value'] is None


def test_bootstrap_includes_sessions_without_group_members():
    f=pd.DataFrame(dict(date=['a','b'],n=[1,1],d=[1,1]))
    result=interval(f,'n','d',dates=['a','b']+[str(i) for i in range(39)])
    assert result['value']==1 and result['valid_draws']<1900 and result['ci95'] is None
