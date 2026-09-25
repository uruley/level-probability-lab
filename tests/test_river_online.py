import copy
import json

import numpy as np
import pandas as pd
import pytest

from level_probability_lab.river_online import (
    Engine, ForecastTail, OnlineModel, atomic_json, live_cycle, loss, outcome, packets,
    panel, read_forecasts, replay, single_writer, stamp,
)


def fixture(offset=0, identity="forecast"):
    t = pd.date_range("2026-09-23T13:30Z", periods=40, freq="min") + pd.Timedelta(minutes=offset)
    bars = [dict(bar_start=x.isoformat(), bar_end=(x+pd.Timedelta(minutes=1)).isoformat(),
                 open=100., high=102., low=98., close=100.+i*.01, volume=10.) for i,x in enumerate(t)]
    row = dict(forecast_id=identity, last_input_timestamp=t[19].isoformat(),
               forecast_created_at=t[20].isoformat(), source="webull_official", symbol="QQQ",
               model_name="Kronos", model_revision="test", input_window=bars[:20],
               target_timestamps=[x.isoformat() for x in t[20:25]],
               sampled_paths=np.tile([100.,102.,98.,101.],(2,5,1)).tolist(),
               forward_context=dict(as_of=t[20].isoformat(),session_vwap_approx=100.,sma200=None))
    return bars,row


def test_dependency_and_features_are_frozen_allowlist():
    bars,row=fixture();p=list(packets(row))[0]
    assert OnlineModel().predict(p['features'])==.5
    other=copy.deepcopy(row);other['actual_close']=999;other['outcomes']={'future':1}
    other['forward_context']['future_close']=999
    assert list(packets(other))==list(packets(row))
    assert all(isinstance(v,float) for v in p['features'].values())
    other['forward_context']['as_of']=bars[-1]['bar_end']
    with pytest.raises(ValueError,match='Future'):list(packets(other))
    other=copy.deepcopy(row);other['input_window'].append(bars[20])
    with pytest.raises(ValueError):list(packets(other))
    other=copy.deepcopy(row);del other['input_window'][-3]
    with pytest.raises(ValueError,match='Missing'):list(packets(other))


def test_each_horizon_uses_own_elapsed_close_and_waits():
    bars,row=fixture()
    for h,p in enumerate(packets(row),1):
        assert outcome(p,bars,stamp(p['due'])-pd.Timedelta(nanoseconds=1)) is None
        r=outcome(p,bars,p['due'])
        assert r['actual_close']==bars[19+h]['close'] and r['label']==1
        missing=[b for b in bars if b != bars[20]]
        assert outcome(p,missing,p['due'])['quality']=='incomplete'


@pytest.mark.parametrize('kind',['neutral_actual','neutral_forecast','incomplete'])
def test_exclusions_never_learn(tmp_path,kind):
    bars,row=fixture();p=list(packets(row))[0]
    if kind=='neutral_actual':bars[20]['close']=p['reference']
    elif kind=='neutral_forecast':p['direction']=0
    else:bars=[]
    e=Engine(tmp_path,'replay');e.predict(p,p['origin']);r=e.resolve(p['id'],bars,p['due'])
    assert r['quality']==kind and r['label'] is None and not r['updated']
    assert e.models[p['model_key']].count==0


def test_saved_prediction_and_score_precede_learning(tmp_path,monkeypatch):
    bars,row=fixture();p=list(packets(row))[0];e=Engine(tmp_path,'replay')
    prediction=e.predict(p,p['origin']);model=e.models[p['model_key']]
    original=model.learn
    def checked(x,y):
        events=[json.loads(f.read_text()) for f in sorted((tmp_path/'events').glob('*.json'))]
        assert [v['kind'] for v in events]==['prediction','outcome']
        assert events[0]['data']['probability']==.5
        assert events[1]['data']['brier']==.25
        original(x,y)
    monkeypatch.setattr(model,'learn',checked)
    assert e.resolve(p['id'],bars,p['origin']) is None and model.count==0
    r=e.resolve(p['id'],bars,p['due'])
    assert r['probability']==prediction['probability']==.5
    assert r['log_loss']==pytest.approx(np.log(2)) and model.count==1


def test_recovery_and_idempotent_restart(tmp_path):
    bars,row=fixture();p=list(packets(row))[0];e=Engine(tmp_path,'replay')
    e.predict(p,p['origin']);e.resolve(p['id'],bars,p['due'])
    expected=e.models[p['model_key']].predict(p['features'])
    restarted=Engine(tmp_path,'replay')
    restarted.predict(p,p['origin']);restarted.resolve(p['id'],bars,p['due'])
    assert restarted.seq==2 and restarted.models[p['model_key']].count==1
    assert restarted.models[p['model_key']].predict(p['features'])==expected


def test_crash_between_score_commit_and_learn_recovers_once(tmp_path,monkeypatch):
    bars,row=fixture();p=list(packets(row))[0];e=Engine(tmp_path,'replay');e.predict(p,p['origin'])
    def crash(*args):raise RuntimeError('crash')
    monkeypatch.setattr(e.models[p['model_key']],'learn',crash)
    with pytest.raises(RuntimeError):e.resolve(p['id'],bars,p['due'])
    restarted=Engine(tmp_path,'replay')
    assert restarted.models[p['model_key']].count==1
    assert restarted.resolve(p['id'],bars,p['due'])['updated']
    assert restarted.models[p['model_key']].count==1


def test_replay_order_overlap_baselines_and_reproducibility(tmp_path):
    bars,a=fixture();_,b=fixture(1,'second')
    first=replay([b,a],lambda p:bars,tmp_path/'a')
    second=replay([a,b],lambda p:bars,tmp_path/'b')
    assert first==second and first['observations']==10
    events=[json.loads(p.read_text()) for p in sorted((tmp_path/'a'/'events').glob('*.json'))]
    assert [stamp(e['time']) for e in events]==sorted(stamp(e['time']) for e in events)
    predictions=[e['data'] for e in events if e['kind']=='prediction' and e['data']['forecast_id']=='second']
    assert next(p for p in predictions if p['horizon']==1)['prior_observations']==1
    assert next(p for p in predictions if p['horizon']==5)['prior_observations']==0
    assert next(p for p in predictions if p['horizon']==1)['historical_probability']==1
    with pytest.raises(ValueError,match='fresh'):replay([a],lambda p:bars,tmp_path/'a')
    for p in (tmp_path/'a'/'events').glob('*.json'):
        assert p.read_bytes()==(tmp_path/'b'/'events'/p.name).read_bytes()


def test_late_live_forecasts_excluded_and_groups_separate(tmp_path):
    bars,row=fixture();items=list(packets(row));e=Engine(tmp_path,'live')
    for p in items:
        saved=e.predict(p,stamp(p['origin'])+pd.Timedelta(minutes=1))
        assert saved['probability'] is None
    for p in items:e.resolve(p['id'],bars,items[-1]['due'])
    assert e.report()['observations']==0
    assert len(e.models)==5
    other=copy.deepcopy(row);other['symbol']='TSLA'
    assert list(packets(other))[0]['model_key']!=items[0]['model_key']


def test_live_durable_queue_delay_and_restart(tmp_path):
    bars,row=fixture();items=list(packets(row));start=stamp(items[0]['origin'])
    (tmp_path/'forecasts.jsonl').write_text(json.dumps(row)+'\n')
    e=Engine(tmp_path/'river_live','live')
    live_cycle(e,tmp_path,start,start+pd.Timedelta(seconds=2))
    assert len(e.predictions)==5
    live_cycle(e,tmp_path,start,start+pd.Timedelta(seconds=65))
    assert not e.outcomes # recorder grace period
    atomic_json(tmp_path/'webull'/'2026-09-23.json',bars)
    live_cycle(e,tmp_path,start,start+pd.Timedelta(seconds=70))
    assert len(e.outcomes)==1
    again=Engine(tmp_path/'river_live','live')
    live_cycle(again,tmp_path,start,start+pd.Timedelta(minutes=6))
    assert again.report()['observations']==5 and len(again.predictions)==5
    assert panel(tmp_path,row['forecast_id'])['status']=='stale / worker stopped'


def test_missing_futures_expire_and_never_relearn_correction(tmp_path):
    bars,row=fixture();p=list(packets(row))[0];e=Engine(tmp_path,'replay')
    e.predict(p,p['origin']);e.resolve(p['id'],[],p['due'])
    assert not e.resolve(p['id'],bars,p['due'])['updated']


def test_worker_failure_is_independent_read_only_panel(tmp_path):
    assert panel(tmp_path)['status']=='disabled'
    folder=tmp_path/'river_live';folder.mkdir();(folder/'status.json').write_text('broken')
    assert panel(tmp_path)['status']=='unavailable'
    # The existing Kronos session has no River worker/model dependency.
    from level_probability_lab.lab import ReplaySession
    bars,_=fixture();frame=pd.DataFrame(bars)
    for col in ('bar_start','bar_end'):frame[col]=pd.to_datetime(frame[col],utc=True)
    frame['session_open']=frame.iloc[0].bar_start;frame['session_close']=frame.iloc[-1].bar_end
    session=ReplaySession(frame,'2026-09-23',lookback=20)
    assert session.advance()['cursor']==20


def test_partial_append_and_writer_lock(tmp_path):
    path=tmp_path/'forecasts.jsonl';path.write_text('{"forecast_id":"a"}\n{"forecast_id":')
    assert read_forecasts(path)==[{'forecast_id':'a'}]
    with single_writer(tmp_path):
        with pytest.raises(OSError):
            with single_writer(tmp_path):pass


def test_reject_backwards_clock(tmp_path):
    _,row=fixture();a,b=list(packets(row))[:2];e=Engine(tmp_path,'replay')
    e.predict(a,stamp(a['origin'])+pd.Timedelta(seconds=10))
    with pytest.raises(ValueError,match='out-of-order'):e.predict(b,b['origin'])


def test_exact_losses_and_forecast_direction():
    assert loss(.7,1)['brier']==pytest.approx(.09)
    assert loss(.7,0)['log_loss']==pytest.approx(-np.log(.3))
    bars,row=fixture();p=list(packets(row))[0];bars[20]['close']=99
    assert outcome(p,bars,p['due'])['label']==0


def test_incremental_tail_defers_concurrent_forecast(tmp_path):
    bars,row=fixture();p=list(packets(row))[0];origin=stamp(p['origin'])
    row['forecast_created_at']=(origin+pd.Timedelta(seconds=2)).isoformat()
    path=tmp_path/'forecasts.jsonl';path.write_text(json.dumps(row)+'\n')
    reader=ForecastTail(path);e=Engine(tmp_path/'river_live','live')
    live_cycle(e,tmp_path,origin,origin,reader)
    assert not e.predictions and len(reader.deferred)==1
    live_cycle(e,tmp_path,origin,origin+pd.Timedelta(seconds=3),reader)
    assert len(e.predictions)==5 and not reader.deferred
    assert reader.read()==[]
    with path.open('a') as f:f.write('{"forecast_id":')
    assert reader.read()==[]
    with path.open('a') as f:f.write('"new"}\n')
    assert reader.read()==[{'forecast_id':'new'}]


def test_long_recovery_matches_uninterrupted_model(tmp_path):
    bars,row=fixture();e=Engine(tmp_path,'replay')
    for i in range(12):
        _,r=fixture(i*6,str(i));p=list(packets(r))[0]
        e.predict(p,p['origin'])
        actual,_=fixture(i*6,str(i))
        e.resolve(p['id'],actual,p['due'])
    restarted=Engine(tmp_path,'replay')
    x=dict(reversed(list(p['features'].items())))
    assert e.models[p['model_key']].predict(x)==restarted.models[p['model_key']].predict(x)


def test_bad_live_features_remain_visible_after_restart(tmp_path):
    _,row=fixture();origin=stamp(row['forecast_created_at']);row['input_window']=[]
    (tmp_path/'forecasts.jsonl').write_text(json.dumps(row)+'\n')
    e=Engine(tmp_path/'river_live','live')
    live_cycle(e,tmp_path,origin,origin)
    restarted=Engine(tmp_path/'river_live','live')
    result=live_cycle(restarted,tmp_path,origin,origin+pd.Timedelta(seconds=2))
    assert len(result['rejected'])==1 and restarted.seq==1
