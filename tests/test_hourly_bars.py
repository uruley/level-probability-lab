import numpy as np
import pandas as pd
import pytest
from level_probability_lab.calendar import session_schedule
from level_probability_lab.hourly_bars import inputs,hours


def history():
    times=[]
    for r in session_schedule('2026-08-01','2026-08-31').itertuples():
        times.extend(pd.date_range(r.market_open,r.market_close,freq='5min',inclusive='left'))
    return pd.DataFrame(dict(bar_start=times,open=100.,high=101.,low=99.,close=100.,volume=10.))


def test_hourly_history_and_future_friday_weekend():
    raw=history();cutoff=pd.Timestamp('2026-08-21T19:30Z')
    window,targets,frame=inputs(raw,cutoff)
    assert len(window)==60 and len(targets)==5
    assert targets[0]==pd.Timestamp('2026-08-24T13:30Z')
    assert window.iloc[-1].bar_end==cutoff
    assert window.iloc[-1].volume==120
    assert (frame.bar_end<=cutoff).all()
    assert not (frame.bar_start.dt.hour==19).any() # short 15:30 closing tail


def test_missing_five_minute_blocks_hourly_forecast():
    raw=history();cutoff=pd.Timestamp('2026-08-21T19:30Z')
    raw=raw.loc[raw.bar_start!=pd.Timestamp('2026-08-21T18:45Z')]
    with pytest.raises(ValueError,match='missing hours'):inputs(raw,cutoff)


def test_mid_hour_uses_last_completed_hour_without_future_data():
    raw=history()
    boundary=pd.Timestamp('2026-08-21T18:30Z')
    before,targets,_=inputs(raw,boundary)
    raw.loc[raw.bar_start>=boundary,['open','high','low','close']]=999.
    midway,later_targets,_=inputs(raw,pd.Timestamp('2026-08-21T18:45Z'))
    pd.testing.assert_frame_equal(before,midway)
    assert targets.equals(later_targets)
    assert midway.iloc[-1].bar_end==boundary


def test_opening_minutes_use_previous_sessions_last_full_hour():
    window,targets,_=inputs(history(),pd.Timestamp('2026-08-24T13:31Z'))
    assert window.iloc[-1].bar_end==pd.Timestamp('2026-08-21T19:30Z')
    assert targets[0]==pd.Timestamp('2026-08-24T13:30Z')
