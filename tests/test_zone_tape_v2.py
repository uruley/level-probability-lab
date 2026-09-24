import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resolve_zone_tape_v2 import resolve_fast
from level_probability_lab.zone_tape import resolve


def test_fast_resolution_preserves_order_and_timestamp_ties():
    rng=np.random.default_rng(8)
    start=pd.Timestamp('2026-06-01T15:30Z')
    for i in range(100):
        tape=pd.DataFrame(dict(ts_recv=[start+pd.Timedelta(seconds=j//2) for j in range(30)],
                               price=rng.choice([99.3,99.95,100.,100.05,100.7],30),size=1.))
        event=dict(cutoff=start,level=100.,risk=1.,price=101. if i%2 else 99.)
        assert resolve_fast(tape,event,start)==resolve(tape,event,start)
