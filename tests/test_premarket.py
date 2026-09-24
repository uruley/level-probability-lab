import numpy as np
import pandas as pd
import pytest
from level_probability_lab.webull_feed import normalize, feed_status
from level_probability_lab.lab import Lab, ReplaySession
from level_probability_lab.ghost_candles.windows import future_session_timestamps


def day(date):
    times=pd.date_range(date+' 04:00',date+' 16:00',freq='min',inclusive='left',tz='America/New_York')
    rows=[dict(timestamp=t.isoformat(),open=100.,high=101.,low=99.,close=100.,volume=20.) for t in times]
    return normalize(rows,1,times[-1]+pd.Timedelta(minutes=2),premarket=True)


def test_premarket_window_has_no_future_or_missing_minutes():
    prior=day('2026-09-23');today=day('2026-09-24')
    s=ReplaySession(today,'2026-09-24',400,warmup=prior,start_open=True)
    s.cursor=299  # 08:59, completed at 09:00 Eastern
    window=s.input_window()
    assert len(window)==400
    assert (window.bar_start<=today.iloc[299].bar_start).all()
    assert (window.bar_start.dt.tz_convert('America/New_York').dt.hour<9).sum()==300
    assert s.state()['can_hour_forecast']
    targets=future_session_timestamps(today,today.iloc[299].bar_start,50)
    assert len(targets)==50 and targets[-1].tz_convert('America/New_York').strftime('%H:%M')=='09:49'
    s.bars=today.drop(index=200).reset_index(drop=True);s.cursor=298
    with pytest.raises(ValueError,match='missing trading minutes'):s.input_window()


def test_live_premarket_gate_and_completion():
    bars=day('2026-09-24').iloc[:1]
    assert not feed_status(bars,pd.Timestamp('2026-09-24 03:59',tz='America/New_York'))['ready']
    assert feed_status(bars,pd.Timestamp('2026-09-24 04:01:10',tz='America/New_York'))['ready']
    assert not feed_status(bars,pd.Timestamp('2026-09-24 04:04',tz='America/New_York'))['ready']
    assert not feed_status(bars,pd.Timestamp('2026-09-24 16:00',tz='America/New_York'))['ready']
    assert not feed_status(bars,pd.Timestamp('2026-09-26 09:00',tz='America/New_York'))['ready']
    row=dict(timestamp='2026-09-24T08:00:00Z',open=100,high=101,low=99,close=100,volume=20)
    with pytest.raises(ValueError,match='completed'):normalize([row],1,pd.Timestamp('2026-09-24T08:01:03Z'),premarket=True)


def test_premarket_saved_forecasts_are_identified(tmp_path,monkeypatch):
    lab=Lab(source=tmp_path/'unused',output=tmp_path)
    s=ReplaySession(day('2026-09-24'),'2026-09-24',400,warmup=day('2026-09-23'),start_open=True)
    s.cursor=299;s.provider='webull_official';s.symbol='TSLA';s.mode='recorded'
    class Model:
        model_name='test-base'
        def forecast_paths(self,window,targets,sample_count,seed):
            assert len(window)==400
            return np.tile([100,101,99,100.5],(sample_count,len(targets),1)),.01
    monkeypatch.setattr(lab,'get_model',lambda key:Model())
    lab.predict(s,'base',10);lab.predict_hour(s,10)
    short=lab.store.all()[0];long=lab.hour_store.all()[0]
    assert short['session_period']=='premarket'
    for row in [short,long]:
        assert row['session_policy']=='pre-rth-v1'
        assert 'pre-rth-v1' in row['forecast_id']
    assert len(long['target_timestamps'])==50
