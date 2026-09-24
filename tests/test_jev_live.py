import json
from types import SimpleNamespace
import pandas as pd
from level_probability_lab.jev_live import LiveObserver, RESERVE

def test_toggle_and_restart_budget(tmp_path):
    observer=LiveObserver(tmp_path,tmp_path)
    s=SimpleNamespace(mode='live',symbol='QQQ',date='2026-09-23',cursor=0,
        bars=pd.DataFrame())
    observer.toggle(s,True)
    assert observer.status(s)['enabled']
    directory=observer.output/s.date/'1430';directory.mkdir(parents=True)
    record=dict(cutoff='2026-09-23T14:30Z',price=100,status='unavailable',outcome='pending',
        targets=[t.isoformat() for t in pd.date_range('2026-09-23T14:30Z',periods=5,freq='min')])
    (directory/'record.json').write_text(json.dumps(record))
    restarted=LiveObserver(tmp_path,tmp_path)
    state=restarted.status(s)
    assert not state['enabled'] and state['reserved_usd']==RESERVE
    s.bars=pd.DataFrame(dict(bar_start=pd.date_range('2026-09-23T14:30Z',periods=5,freq='min'),
        bar_end=pd.date_range('2026-09-23T14:31Z',periods=5,freq='min'),close=[100,100,100,100,101]))
    s.cursor=4
    assert restarted.status(s)['rows'][0]['outcome']=='bull'
    assert json.loads((directory/'record.json').read_text())['outcome']=='bull'

def test_gap_is_incomplete(tmp_path):
    observer=LiveObserver(tmp_path,tmp_path)
    directory=observer.output/'2026-09-23'/'1430';directory.mkdir(parents=True)
    (directory/'record.json').write_text(json.dumps(dict(price=100,status='ready',outcome='pending',
        targets=[t.isoformat() for t in pd.date_range('2026-09-23T14:30Z',periods=5,freq='min')])))
    s=SimpleNamespace(mode='live',symbol='QQQ',date='2026-09-23',cursor=0,
        bars=pd.DataFrame(dict(bar_start=[pd.Timestamp('2026-09-23T14:34Z')],bar_end=[pd.Timestamp('2026-09-23T14:35Z')],close=[100])))
    assert observer.status(s)['rows'][0]['outcome']=='incomplete'
