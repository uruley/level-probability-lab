"""Independent artifact checks for the completed May/June build."""
import json
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, load_day
from level_probability_lab.calendar import session_schedule
from level_probability_lab.companion_features import build_features


def main():
    out=ROOT/'data/companion_v02/may_june'
    report=json.loads((out/'report.json').read_text())
    source=ROOT/'data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet'
    checks=0
    for month in ['may','june']:
        f=pd.read_parquet(out/f'features_{month}.parquet')
        l=pd.read_parquet(out/f'labels_{month}.parquet')
        assert f.origin_id.is_unique and l.origin_id.is_unique
        assert set(f.origin_id)==set(l.origin_id)
        assert not set(l.columns).intersection(f.columns)-{'origin_id'}
        assert np.isfinite(f.select_dtypes('number')).all().all()
        for day, rows in f.groupby(f.forecast_time_utc.str[:10]):
            bars=load_day(source,day)
            calendar=session_schedule(pd.Timestamp(day)-pd.Timedelta(days=10),pd.Timestamp(day)-pd.Timedelta(days=1))
            previous=load_day(source,pd.Timestamp(calendar.index[-1]).strftime('%Y-%m-%d'))
            selected=rows.iloc[0]
            package=json.loads((out/'input_packages'/(selected.origin_id+'.json')).read_text())
            rebuilt=build_features(package,bars,previous)
            pd.testing.assert_series_equal(pd.Series(rebuilt),selected.rename(None),check_names=False)
            cutoff=pd.Timestamp(selected.forecast_time_utc)
            label=l.loc[l.origin_id==selected.origin_id].iloc[0]
            actual=bars.loc[bars.bar_end==cutoff+pd.Timedelta(minutes=5),'close'].iloc[0]
            assert actual==label.actual_close_p5
            assert pd.Timestamp(label.label_available_at)==cutoff+pd.Timedelta(minutes=5)
            checks+=1
    assert checks==41 and report['missing_forecasts']==0 and not report['excluded']
    result={'session_feature_rebuild_checks':checks,'label_timing_checks':checks,
            'feature_label_key_checks':'passed','finite_values':'passed','outcome_column_isolation':'passed'}
    (out/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
