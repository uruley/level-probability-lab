import hashlib
import json
import pytest
from level_probability_lab.jev_context import context_pair

def fixture():
    row=dict(origin='2026-05-01T15:29:00+00:00', model='base',origin_close=100,input_sha256='input',
        targets=[f'2026-05-01T15:{m}:00+00:00' for m in range(30,35)],
        sampled_ohlc=[[[100,101,99,100]]*5])
    raw=json.dumps(row).encode()
    saved=dict(origin=row['origin'],input_sha256='input',forecast_sha256=hashlib.sha256(raw).hexdigest(),
        context=dict(as_of='2026-05-01T15:30Z',reference=100,version='test',convention='completed',
        history_evidence={'hourly':[dict(end='2026-05-01T15:30Z')]},
        levels=[dict(name='SMA 20',timeframe='hourly',value=99,distance=1,available_at='2026-05-01T15:30Z')]))
    return row,raw,saved

def seal(saved):
    saved.pop('context_id',None)
    saved['context_id']=hashlib.sha256(json.dumps(saved,sort_keys=True,allow_nan=False).encode()).hexdigest()

def test_pair_changes_only_context():
    row,raw,saved=fixture(); seal(saved)
    base,enriched=context_pair(row,saved,raw)
    assert {k:v for k,v in enriched.items() if k!='market_context'} == {k:v for k,v in base.items() if k!='market_context'}
    assert enriched['market_context']['levels'][0]['distance_bp']==100

@pytest.mark.parametrize('failure',['future_level','future_history','wrong_price','bad_hash'])
def test_rejects_unsafe_context(failure):
    row,raw,saved=fixture()
    if failure=='future_level': saved['context']['levels'][0]['available_at']='2026-05-01T15:31Z'
    if failure=='future_history': saved['context']['history_evidence']['hourly'][0]['end']='2026-05-01T15:31Z'
    if failure=='wrong_price': saved['context']['reference']=101
    seal(saved)
    if failure=='bad_hash': saved['context_id']='bad'
    with pytest.raises(ValueError): context_pair(row,saved,raw)
