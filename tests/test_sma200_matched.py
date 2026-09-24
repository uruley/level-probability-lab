import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sma200_matched_v1 import match_cases
from level_probability_lab.calendar import session_schedule


def event(date,minute,level):
    t=pd.Timestamp(date+'T15:30Z')+pd.Timedelta(minutes=minute)
    return dict(id=t.isoformat(),cutoff=t.isoformat(),date=date,level=level,price=100.,risk=1.)

def test_matches_preserve_distance_and_exclude_close_and_same_day():
    schedule=session_schedule('2026-06-01','2026-06-03')
    events=[event(d,m,l) for d,l in [('2026-06-01',99.),('2026-06-02',102.),('2026-06-03',98.)] for m in [0,5,75,150,225]]
    pairs=match_cases(events,schedule)
    assert len(pairs)==9  # 225-minute origin cannot contain the full horizon
    for p in pairs:
        a,b=p['case'],p['control']
        if b is None:continue
        assert a['date']!=b['date']
        assert (a['price']-a['level'])/a['risk']==(b['price']-b['level'])/b['risk']
        assert abs(b['level']-b['actual_sma200'])/b['risk']>=1
    assert pairs==match_cases(list(reversed(events)),schedule)


def test_no_match_stays_unmatched_without_relaxation():
    e=event('2026-06-01',0,99.)
    assert match_cases([e],session_schedule('2026-06-01','2026-06-01'))==[dict(case=e,control=None)]
