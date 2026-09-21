import json
import numpy as np
import pandas as pd
import pytest
from level_probability_lab.webull_feed import Feed,normalize,feed_status
from level_probability_lab.lab import Lab


def records(start='2026-09-18T13:30Z',n=390,minutes=1):
    return [dict(timestamp=t.isoformat(),open=100.,high=101.,low=99.,close=100.,volume=50.)
            for t in pd.date_range(start,periods=n,freq=f'{minutes}min')]


def test_only_completed_regular_candles_with_settlement_delay():
    rows=records(n=5)
    frame=normalize(rows,1,pd.Timestamp('2026-09-18T13:33:03Z'))
    assert len(frame)==2 and frame.iloc[-1].bar_end==pd.Timestamp('2026-09-18T13:32Z')
    with pytest.raises(ValueError,match='duplicate'):normalize(rows+rows[:1],1,pd.Timestamp('2026-09-18T20:01Z'))
    rows[0]['high']=98
    with pytest.raises(ValueError,match='invalid'):normalize(rows,1,pd.Timestamp('2026-09-18T20:01Z'))


def test_stale_closed_and_error_never_allow_live_forecasts():
    frame=normalize(records(),1,pd.Timestamp('2026-09-18T20:01Z'))
    assert feed_status(frame,pd.Timestamp('2026-09-20T15:00Z'))['status']=='market_closed'
    early=frame.iloc[:120]
    assert feed_status(early,pd.Timestamp('2026-09-18T15:30:20Z'))['ready']
    assert feed_status(early,pd.Timestamp('2026-09-18T15:33:00Z'))['status']=='stale'
    assert not feed_status(early,pd.Timestamp('2026-09-18T15:30:20Z'),'Connection failed')['ready']


def test_recordings_and_hour_gaps_are_preserved(tmp_path):
    feed=Feed(tmp_path,tmp_path)
    now=pd.Timestamp('2026-09-18T20:01Z')
    feed.frames={'M1':normalize(records(),1,now),'M5':normalize(records(n=78,minutes=5),5,now)}
    feed.frames['M5']=feed.frames['M5'].drop(index=60)
    feed.save(dict(provider='webull_official',symbol='QQQ',frames={}),now)
    assert feed.dates()==['2026-09-18']
    assert len(feed.recorded('2026-09-18'))==390
    assert feed.hour_history().iloc[60].close!=feed.hour_history().iloc[60].close
    restarted=Feed(tmp_path,tmp_path)
    assert len(restarted.hour_history())==78 and pd.isna(restarted.hour_history().iloc[60].close)
    with pytest.raises(ValueError):feed.recorded('../secrets')


def test_failed_worker_never_falls_back(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:type('Result',(),{'stdout':json.dumps(dict(ok=False,error='Authorization needed'))})())
    feed=Feed(tmp_path,tmp_path)
    with pytest.raises(ValueError,match='Authorization needed'):feed.fetch()
    assert feed.error and not feed.frames and not feed.dates()


def test_live_session_cannot_step_or_forecast_closed_market(tmp_path,monkeypatch):
    lab=Lab(source=tmp_path/'unused',output=tmp_path)
    frame=normalize(records(),1,pd.Timestamp('2026-09-18T20:01Z'))
    monkeypatch.setattr(lab.webull,'fetch',lambda:dict(M1=frame))
    import level_probability_lab.webull_feed as module
    monkeypatch.setattr(module,'feed_status',lambda *a:dict(ready=False,status='market_closed',message='Market closed'))
    state=lab.poll_live();session=lab.sessions[state['session_id']]
    assert state['mode']=='live' and not state['can_forecast'] and not state['can_hour_forecast']
    with pytest.raises(ValueError,match='Webull supplies'):session.advance()
    with pytest.raises(ValueError,match='Market closed'):lab.predict(session,'base',10)
    with pytest.raises(ValueError,match='Market closed'):lab.predict_hour(session,10)
    assert not lab.store.all() and not lab.hour_store.all()


def test_webull_forecast_ids_and_inputs_are_isolated(tmp_path,monkeypatch):
    lab=Lab(source=tmp_path/'unused',output=tmp_path)
    frame=normalize(records(),1,pd.Timestamp('2026-09-18T20:01Z'))
    lab.webull.output.mkdir();(lab.webull.output/'2026-09-18.json').write_text(frame.to_json(orient='records',date_format='iso'))
    state=lab.create_recorded('2026-09-18',120);session=lab.sessions[state['session_id']]
    assert session.cursor == 0
    session.cursor=119
    class Model:
        model_name='test-base'
        def forecast_paths(self,window,targets,sample_count,seed):return np.tile([100,101,99,100.5],(sample_count,5,1)),.01
    monkeypatch.setattr(lab,'get_model',lambda key:Model())
    result=lab.predict(session,'base',10)
    assert result['forecast_id'].startswith('webull|')
    assert lab.store.all()[0]['source']=='webull_official'
    assert not list((tmp_path/'input_packages').glob('*'))
    with pytest.raises(ValueError,match='archive trade totals'):lab.predict(session,'base',10,'trades')


def test_tsla_storage_is_separate(tmp_path):
    q=Feed(tmp_path,tmp_path)
    t=Feed(tmp_path,tmp_path,'TSLA')
    assert t.symbol=='TSLA' and t.output==q.output/'TSLA'
    assert q.output!=t.output
    with pytest.raises(ValueError):Feed(tmp_path,tmp_path,'../invalid')
