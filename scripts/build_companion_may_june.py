"""Expand v0.2 over frozen May/June Base forecasts. No fitting or network."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, load_day
from level_probability_lab.calendar import session_schedule
from level_probability_lab.input_package import build_package, canonical
from level_probability_lab.companion_features import build_features


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    archive=ROOT/'data/kronos_baseline_v1'
    cfg=json.loads((archive/'frozen_config.json').read_text())
    assert (cfg['lookback'],cfg['sample_count'],cfg['seed'])==(120,25,42)
    source=ROOT/cfg['source']
    if digest(source)!=cfg['source_sha256']:raise ValueError('Candle source hash changed')
    trade_path=ROOT/'data/trades_study/trade_features_may_june.parquet'
    audit=json.loads((trade_path.parent/'trade_feature_audit.json').read_text())
    if not audit['accepted'] or digest(trade_path)!=audit['features_sha256']:raise ValueError('Trade audit mismatch')
    trades=pd.read_parquet(trade_path)
    out=ROOT/'data/companion_v02/may_june'
    out.mkdir(parents=True,exist_ok=True)
    (out/'input_packages').mkdir(exist_ok=True)
    schedule=session_schedule('2026-04-20','2026-06-30')
    dates=[pd.Timestamp(x).strftime('%Y-%m-%d') for x in schedule.index]
    features,labels,excluded,coverage=[],[],[],[]
    manifest=[]
    for day in dates:
        if day<'2026-05-01':continue
        bars=load_day(source,day)
        previous=load_day(source,dates[dates.index(day)-1])
        daily_trades=trades.loc[trades.bar_start.isin(bars.bar_start)]
        files=sorted((archive/'forecasts/base').glob(day.replace('-','')+'T*.json'))
        count_before=len(features)
        for path in files:
            r=json.loads(path.read_text())
            if r['date']!=day or r['model']!='base':raise ValueError('Forecast metadata mismatch')
            origin=pd.Timestamp(r['origin'])
            window=bars.loc[bars.bar_start<=origin].tail(120)
            calculated=hashlib.sha256(window[['bar_start','open','high','low','close','volume']].to_csv(index=False).encode()).hexdigest()
            if calculated!=r['input_sha256']:raise ValueError('Frozen forecast input mismatch')
            arr=np.asarray(r['sampled_ohlc'])
            if arr.shape!=(25,5,4) or not np.isfinite(arr).all():raise ValueError('Invalid paths')
            window_records=window[['bar_start','open','high','low','close','volume']].copy()
            window_records['bar_start']=window_records.bar_start.map(lambda t:t.isoformat())
            window_records=window_records.to_dict('records')
            record=dict(forecast_id='baseline-v1|base|'+r['origin'],input_window=window_records,
                        last_input_timestamp=r['origin'],target_timestamps=r['targets'],
                        model_name='NeoQuasar/Kronos-base',model_revision=cfg['base_revision'],
                        random_seed=42,sample_count=25,sampled_paths=r['sampled_ohlc'],amount_mode='approximate')
            provenance={'forecast_file':str(path.relative_to(ROOT)), 'forecast_sha256':digest(path),
                        'candle_source_sha256':cfg['source_sha256'],'trade_features_sha256':audit['features_sha256'],
                        'tokenizer_revision':cfg['tokenizer_revision'], 'frozen_config_sha256':digest(archive/'frozen_config.json')}
            manifest.append(provenance)
            package=build_package(record,daily_trades,provenance)
            try:
                row=build_features(package,bars,previous)
            except ValueError as exc:
                excluded.append({'date':day,'origin':r['origin'],'reason':str(exc)})
                continue
            # One independent future-value mutation per session.
            if len(features)==count_before:
                altered=bars.copy()
                altered.loc[altered.bar_end>pd.Timestamp(package['cutoff']),['open','high','low','close','volume']]=1e8
                pd.testing.assert_series_equal(pd.Series(row),pd.Series(build_features(package,altered,previous)))
            text=canonical(package)
            package_path=out/'input_packages'/(package['package_id']+'.json')
            if package_path.exists():
                if package_path.read_text()!=text:raise ValueError('Package changed')
            else:package_path.write_text(text)
            features.append(row)
            target=pd.to_datetime(r['targets'],utc=True)
            future=bars.loc[bars.bar_start.isin(target)].sort_values('bar_start')
            eligible=list(future.bar_start)==list(target)
            actual=float(future.iloc[-1].close) if eligible else None
            d=float(abs(np.median(arr[:,4,3])-actual)-abs(window.iloc[-1].close-actual)) if eligible else None
            tie=eligible and abs(d)<=1e-8
            labels.append(dict(origin_id=package['package_id'],actual_close_p5=actual,error_difference=d,
                               label_eligible=eligible,tie_flag=tie,y_kronos_wins=None if not eligible or tie else int(d<0),
                               label_available_at=(target[-1]+pd.Timedelta(minutes=1)).isoformat()))
        expected=len(pd.date_range(bars.iloc[0].session_open+pd.Timedelta(minutes=119),bars.iloc[0].session_close-pd.Timedelta(minutes=6),freq='5min'))
        coverage.append(dict(date=day,expected_origins=expected,saved_forecasts=len(files),built_rows=len(features)-count_before))
        print(f'{day}: {len(features)-count_before}/{len(files)} rows',flush=True)
    f=pd.DataFrame(features);l=pd.DataFrame(labels)
    assert f.origin_id.is_unique and set(f.origin_id)==set(l.origin_id)
    assert all(pd.to_datetime(f.forecast_time_utc,utc=True).dt.month.isin([5,6]))
    for month,name in [(5,'may'),(6,'june')]:
        part=f.loc[pd.to_datetime(f.forecast_time_utc,utc=True).dt.month==month]
        part.to_parquet(out/f'features_{name}.parquet',index=False)
        part.to_csv(out/f'features_{name}.csv',index=False)
        l.loc[l.origin_id.isin(part.origin_id)].to_parquet(out/f'labels_{name}.parquet',index=False)
    report={'scope':'Development build only; no fitting or predictive scoring','rows':len(f),'sessions':len(coverage),
            'coverage':coverage,'excluded':excluded,'complete_trade_rows':int(f.ts_block_available.sum()),
            'complete_candle_rows':int(f.candle_features_complete.sum()),
            'null_counts':{k:int(v) for k,v in f.isna().sum().items() if v},
            'infinite_numeric_values':int(np.isinf(f.select_dtypes('number')).sum().sum()),
            'missing_forecasts':sum(max(0,r['expected_origins']-r['saved_forecasts']) for r in coverage),
            'builder_sha256':digest(Path(__file__)),'feature_builder_sha256':digest(ROOT/'src/level_probability_lab/companion_features.py'),
            'forecasts':manifest}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['coverage','forecasts']},indent=2))


if __name__=='__main__':main()
