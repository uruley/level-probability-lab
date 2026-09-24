from copy import deepcopy
import pandas as pd
import pytest
from level_probability_lab.bull_bear_truth import snapshot, score, persist, replay

META=dict(experiment_id='fixture-v1',source='offline-test',price_policy='unadjusted fixture',availability_policy='bar-end fixture',code_version='test-v1')
ORIGIN=pd.Timestamp('2026-08-14T14:00Z')

def bars():
    return [dict(symbol='QQQ',source_id=f'bar-{i}',bar_start=t.isoformat(),bar_end=(t+pd.Timedelta(minutes=1)).isoformat(),available_at=(t+pd.Timedelta(minutes=1)).isoformat(),open=100,high=102,low=98,close=100,volume=10) for i,t in enumerate(pd.date_range(ORIGIN-pd.Timedelta(minutes=2),periods=9,freq='min'))]

def freeze(raw):return snapshot(raw,ORIGIN,ORIGIN,lookback=2,**META)

@pytest.mark.parametrize('close,label', [('100.1','neutral'),('99.9','neutral'),('100.100001','bull'),('99.899999','bear'),('100','neutral')])
def test_exact_boundaries(close,label):
    raw=bars();f=freeze(raw);raw[6]['close']=close
    result=score(f,raw,ORIGIN+pd.Timedelta(minutes=5))
    assert result['status']=='complete' and result['label']==label
    assert len(result['future_bars'])==5


def test_future_invariance_and_no_early_scoring():
    raw=bars();f=freeze(raw)
    for row in raw[2:]:row['close']=101
    assert freeze(raw)==f
    assert score(f,raw,ORIGIN+pd.Timedelta(minutes=4))['label'] is None
    assert score(f,raw,ORIGIN+pd.Timedelta(minutes=4))['status']=='pending'

@pytest.mark.parametrize('kind',['missing','delayed','corrected','duplicate','partial'])
def test_bad_future_never_neutral_or_shifted(kind):
    raw=bars();f=freeze(raw)
    if kind=='missing':raw.pop(4)
    elif kind=='delayed':raw[4]['available_at']=(ORIGIN+pd.Timedelta(minutes=8)).isoformat()
    elif kind=='corrected':raw[4]['corrected']=True
    elif kind=='duplicate':raw.append(deepcopy(raw[4]))
    else:raw[4]['bar_end']=raw[4]['bar_start']
    r=score(f,raw,ORIGIN+pd.Timedelta(minutes=5))
    assert r['status']=='unscorable' and r['label'] is None and r['p5'] is None

@pytest.mark.parametrize('kind',['missing','delayed','corrected','duplicate','partial'])
def test_bad_input_rejected(kind):
    raw=bars()
    if kind=='missing':raw.pop(0)
    elif kind=='delayed':raw[0]['available_at']=(ORIGIN+pd.Timedelta(seconds=1)).isoformat()
    elif kind=='corrected':raw[0]['corrected']=True
    elif kind=='duplicate':raw.append(deepcopy(raw[0]))
    else:raw[0]['bar_end']=raw[0]['bar_start']
    with pytest.raises(ValueError):freeze(raw)


def test_origin_revision_and_immutable_repeat(tmp_path):
    raw=bars();f=freeze(raw);now=ORIGIN+pd.Timedelta(minutes=5)
    r=score(f,raw,now);persist(tmp_path,f,r)
    before=(tmp_path/'outcomes.jsonl').read_bytes()
    persist(tmp_path,f,r);assert (tmp_path/'outcomes.jsonl').read_bytes()==before
    raw[1]['close']=101
    correction=score(f,raw,now+pd.Timedelta(seconds=1));assert correction['status']=='unscorable'
    persist(tmp_path,f,correction)
    assert (tmp_path/'outcomes.jsonl').read_bytes().startswith(before)
    bad=deepcopy(f);bad['origin_close']='105'
    with pytest.raises(ValueError):score(bad,raw,now)


def test_session_and_timezone_guards():
    for origin in ['2026-08-14T19:56Z','2026-08-15T14:00Z','2026-08-14T14:00']:
        with pytest.raises(ValueError):snapshot(bars(),origin,origin,**META)
    with pytest.raises(ValueError):snapshot(bars(),ORIGIN,ORIGIN+pd.Timedelta(minutes=1),**META)


def test_replay_deterministic(tmp_path):
    kwargs=dict(as_of=ORIGIN+pd.Timedelta(minutes=5),output=tmp_path,lookback=2,**META)
    a=replay(bars(),[(ORIGIN,ORIGIN)],**kwargs)
    assert replay(bars(),[(ORIGIN,ORIGIN)],**kwargs)==a
