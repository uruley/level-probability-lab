"""Build v0.2 on 12 existing May 1 forecasts; no fitting or downloads."""
import hashlib
import json
import numpy as np
import pandas as pd
from level_probability_lab.lab import ROOT, load_day
from level_probability_lab.calendar import session_schedule
from level_probability_lab.input_package import save_package
from level_probability_lab.companion_features import build_features


def main():
    source=ROOT/'data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet'
    ledger=ROOT/'data/trade_amount_v1/development_check/forecasts.jsonl'
    out=ROOT/'data/companion_v02/dry_run_may01'
    out.mkdir(parents=True,exist_ok=True)
    bars=load_day(source,'2026-05-01')
    schedule=session_schedule('2026-04-20','2026-04-30')
    previous_date=pd.Timestamp(schedule.index[-1]).strftime('%Y-%m-%d')
    previous=load_day(source,previous_date)
    features,labels=[],[]
    for line in ledger.read_text().splitlines():
        row=json.loads(line)
        if row.get('amount_mode','approximate')!='approximate':continue
        if not row['last_input_timestamp'].startswith('2026-05-01'):raise ValueError('May 1 only')
        pid=save_package(row,ROOT,out)
        package=json.loads((out/'input_packages'/f'{pid}.json').read_text())
        result=build_features(package,bars,previous)
        # Prove later candle values cannot affect feature construction.
        altered=bars.copy()
        altered.loc[altered.bar_end>pd.Timestamp(package['cutoff']),['open','high','low','close','volume']]=1e8
        assert result==build_features(package,altered,previous)
        features.append(result)
        # Outcome assembly is deliberately outside the feature builder.
        target_starts=pd.to_datetime(row['target_timestamps'],utc=True)
        future=bars.loc[bars.bar_start.isin(target_starts)].sort_values('bar_start')
        eligible=list(future.bar_start)==list(target_starts)
        actual=float(future.iloc[-1].close) if eligible else None
        pred=float(np.median(np.asarray(row['sampled_paths'])[:,4,3]))
        current=row['input_window'][-1]['close']
        difference=abs(pred-actual)-abs(current-actual) if eligible else None
        tie=eligible and abs(difference)<=1e-8
        labels.append(dict(origin_id=pid,actual_close_p5=actual,label_eligible=eligible,
                           label_available_at=(target_starts[-1]+pd.Timedelta(minutes=1)).isoformat(),
                           error_difference=difference,tie_flag=tie,
                           y_kronos_wins=None if not eligible or tie else int(difference<0)))
    frame=pd.DataFrame(features)
    assert len(frame)==12 and frame.origin_id.is_unique
    assert frame.ts_block_available.all() and frame.candle_features_complete.all()
    assert not frame.isna().any().any()
    frame.to_parquet(out/'features.parquet',index=False)
    frame.to_csv(out/'features.csv',index=False)
    pd.DataFrame(labels).to_parquet(out/'labels.parquet',index=False)
    report={'scope':'May 1 development dry run, not training or evaluation',
            'rows':len(frame),'columns':list(frame.columns),'previous_session':previous_date,
            'future_mutation_checks_passed':12,'complete_trade_rows':int(frame.ts_block_available.sum()),
            'all_values_finite':bool(np.isfinite(frame.select_dtypes('number')).all().all()),
            'label_file_separate':True,'seed':42,'paths':25,'amount_mode':'approximate',
            'source_forecasts':str(ledger.relative_to(ROOT))}
    for key,path in [('source_forecasts',ledger),('feature_builder',ROOT/'src/level_probability_lab/companion_features.py')]:
        with path.open('rb') as f:report[key+'_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
