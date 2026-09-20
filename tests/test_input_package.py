import copy
import pandas as pd
from level_probability_lab.input_package import build_package, save_outcomes
from level_probability_lab.trade_features import FEATURES


def fixture():
    stamp=pd.Timestamp('2026-05-01T14:00Z')
    candle=dict(bar_start=stamp.isoformat(),open=10.,high=11.,low=9.,close=10.,volume=100)
    forecast=dict(forecast_id='test',input_window=[candle],last_input_timestamp=stamp.isoformat(),target_timestamps=[t.isoformat() for t in pd.date_range(stamp+pd.Timedelta(minutes=1),periods=5,freq='min')],model_name='test',model_revision='fixed',random_seed=42,sample_count=1,sampled_paths=[[[10.,11.,9.,10.]]*5])
    trade={**candle,'bar_start':stamp,'available_at':stamp+pd.Timedelta(minutes=1),'last_received_at':stamp+pd.Timedelta(seconds=59),'feature_eligible':True,'reconciled':True,**{k:1. for k in FEATURES}}
    return forecast,pd.DataFrame([trade])


def test_future_trade_changes_do_not_change_package():
    f,t=fixture(); future=t.copy();future['bar_start']+=pd.Timedelta(minutes=1);future['trade_count']=999
    a=build_package(f,t); b=build_package(f,pd.concat([t,future]))
    assert a==b
    assert a['companion_inputs']['trade_status']=='complete'
    assert 'actual_close' not in a
    assert a['kronos_inputs']['candles'][0]['amount']==1000


def test_late_bad_missing_and_mismatched_trade_features_are_not_exposed():
    f,t=fixture()
    for column,value in [('available_at',pd.Timestamp('2026-05-01T14:02Z')),('feature_eligible',False),('volume',99),('trade_count',float('nan'))]:
        bad=t.copy();bad[column]=value
        p=build_package(f,bad)
        assert p['companion_inputs']['trade_minutes'][0]['features'] is None
        assert p['companion_inputs']['trade_status']=='incomplete'
    assert build_package(f,t.iloc[:0])['companion_inputs']['trade_minutes'][0]['status']=='missing'


def test_outcomes_are_separate_and_pending_stays_null(tmp_path):
    import json
    save_outcomes({'clock':'2026-05-01T14:01Z','forecasts':[dict(input_package_id='abc',targets=['2026-05-01T14:01Z'],actual=[None],outcome_status=['pending'])]},tmp_path)
    row=json.loads(next((tmp_path/'outcomes').glob('*.json')).read_text())
    assert row['actual_close']==[None]
