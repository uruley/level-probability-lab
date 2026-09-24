import pandas as pd
import pytest
from level_probability_lab.opening_window import session_window
from level_probability_lab.lab import ReplaySession
from level_probability_lab.calendar import session_schedule


def bars(date):
    r=session_schedule(date,date).iloc[0]
    t=pd.date_range(r.market_open,r.market_close,freq='min',inclusive='left')
    return pd.DataFrame(dict(bar_start=t,bar_end=t+pd.Timedelta(minutes=1),
        open=100.,high=101.,low=99.,close=100.,volume=10.,
        session_open=r.market_open,session_close=r.market_close))


def test_opening_uses_friday_history_without_monday_future():
    prior=bars('2026-09-18');today=bars('2026-09-21')
    s=ReplaySession(today,'2026-09-21',120,warmup=prior,start_open=True)
    w=s.input_window()
    assert s.cursor==0 and len(w)==120
    assert w.iloc[-1].bar_start==today.iloc[0].bar_start
    assert w.iloc[-2].bar_start==prior.iloc[-1].bar_start
    assert s.state()['clock']=='2026-09-21T13:31:00+00:00'
    assert s.state()['can_forecast']

    for _ in range(4): s.advance()
    assert s.state()['can_hour_forecast']


def test_missing_trading_minute_cannot_be_replaced_by_older_bar():
    prior=bars('2026-09-18').drop(index=385);today=bars('2026-09-21')
    with pytest.raises(ValueError,match='missing trading minutes'):
        session_window(pd.concat([prior,today]),today.iloc[0].bar_start,120)


def test_missing_warmup_does_not_skip_open_and_recovers():
    s=ReplaySession(bars('2026-09-21'),'2026-09-21',120,start_open=True)
    assert s.cursor==0 and not s.state()['can_forecast']
    s.cursor=119
    assert s.state()['can_forecast']

def test_chart_warmup_is_past_only_and_requires_complete_grid():
    prior=bars('2026-09-18');today=bars('2026-09-21')
    s=ReplaySession(today,'2026-09-21',120,warmup=prior,start_open=True)
    history=s.state()['chart_warmup']
    assert len(history)==199
    assert all(pd.Timestamp(r['t'])<today.iloc[0].bar_start for r in history)
    assert history[-1]['t']==prior.iloc[-1].bar_start.isoformat()
    s.warmup=prior.drop(index=385)
    assert s.state()['chart_warmup']==[]


def test_400_at_open_needs_two_prior_sessions():
    today=bars('2026-09-21');prior=bars('2026-09-18');older=bars('2026-09-17')
    s=ReplaySession(today,'2026-09-21',400,warmup=pd.concat([older,prior]),start_open=True)
    w=s.input_window()
    assert len(w)==400 and len(w[w.bar_start<today.iloc[0].bar_start])==399
    assert w.iloc[-1].bar_start==today.iloc[0].bar_start
    assert s.state()['can_hour_forecast']
    s.warmup=prior
    assert not s.state()['can_hour_forecast']
