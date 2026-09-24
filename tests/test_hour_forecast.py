import json
import numpy as np
import pandas as pd
import pytest
from level_probability_lab.hour_forecast import aggregate, input_window, public, availability, save_outcomes
from level_probability_lab.lab import Lab, ReplaySession


def fixture():
    starts=pd.to_datetime(['2026-08-12T13:30Z','2026-08-13T13:30Z','2026-08-14T13:30Z'])
    schedule=pd.DataFrame(dict(market_open=starts,market_close=starts+pd.Timedelta(minutes=390)))
    frames=[]
    for start in starts:
        times=pd.date_range(start,periods=390,freq='min')
        frames.append(pd.DataFrame(dict(bar_start=times,bar_end=times+pd.Timedelta(minutes=1),
            open=100.,high=101.,low=99.,close=100.,volume=10,session_open=start,session_close=start+pd.Timedelta(minutes=390))))
    return pd.concat(frames,ignore_index=True),schedule,frames[-1]


def test_completed_buckets_only_and_gaps_do_not_disappear():
    raw,schedule,day=fixture(); history=aggregate(raw,schedule)
    window,targets=input_window(history,day.iloc[:120])
    assert len(window)==120 and len(targets)==12
    assert window.bar_end.max()==targets[0]==day.iloc[119].bar_end
    assert window.iloc[-1].volume==50
    mutated=raw.copy();mutated.loc[mutated.bar_start>=targets[0],['open','high','low','close']]=999.
    pd.testing.assert_frame_equal(window,input_window(aggregate(mutated,schedule),day.iloc[:120])[0])
    broken=raw.loc[raw.bar_start!=day.iloc[110].bar_start]
    with pytest.raises(ValueError,match='missing bars'): input_window(aggregate(broken,schedule),day.iloc[:120])
    assert not availability(day.iloc[:121])[0]
    assert not availability(day.iloc[:335])[0]


def test_fifty_is_separate_frozen_and_only_scores_revealed_minutes(tmp_path):
    raw,schedule,day=fixture(); history=aggregate(raw,schedule)
    lab=Lab(source=tmp_path/'unused',output=tmp_path);lab.hour_history=lambda date:history
    calls=[]
    class Model:
        model_name='test-base'
        def forecast_paths(self,window,targets,sample_count,seed):
            calls.append(window.copy());return np.tile([100,102,98,100.5],(sample_count,50,1)),.01
    lab.get_model=lambda key:Model()
    session=ReplaySession(day,'2026-08-14',120)
    a=lab.predict_hour(session,10);b=lab.predict_hour(session,10)
    assert a['hour_forecast_id']==b['hour_forecast_id'] and len(calls)==1
    assert not a['forecasts'] and a['metrics']['scored']==0 and not lab.store.all()
    row=lab.hour_store.all()[0];original=json.dumps(row)
    assert row['input_minutes']==1 and row['horizon_minutes']==50
    assert len(row['target_timestamps'])==50
    assert (calls[0].bar_end-calls[0].bar_start==pd.Timedelta(minutes=1)).all()
    assert calls[0].bar_end.max()<=pd.Timestamp(row['as_of'])
    assert a['hour_forecasts'][0]['outcome']['actual']==dict(high=None,low=None,close=None)
    assert a['hour_forecasts'][0]['outcome']['status']=='pending'
    assert a['hour_forecasts'][0]['outcome']['observed_minutes']==0
    partial=public(row,day.iloc[:125]);assert partial['outcome']['status']=='pending'
    assert partial['outcome']['actual']['close'] is None
    assert all(v is None for v in partial['outcome']['errors'].values())
    final=public(row,day.iloc[:170]);assert final['outcome']['status']=='complete'
    assert final['outcome']['observed_minutes']==50 and final['outcome']['errors']==dict(high=1.,low=1.,close=.5)
    assert final['outcome']['flat_close_error']==0
    assert public(row,day.iloc[:170].drop(index=125))['outcome']['status']=='incomplete'
    assert json.dumps(lab.hour_store.all()[0])==original
    save_outcomes(dict(clock=day.iloc[169].bar_end.isoformat(),hour_forecasts=[final]),tmp_path)
    assert len(list((tmp_path/'hour_outcomes').glob('*.json')))==1
    assert len(Lab(source=tmp_path/'unused',output=tmp_path).hour_store.all())==1
