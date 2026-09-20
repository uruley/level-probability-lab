"""Companion v0.2: features only; no outcome files or fitting dependencies."""
import numpy as np
import pandas as pd


def aggregate_completed(bars, opening, cutoff, minutes):
    result = []
    for start in pd.date_range(opening, cutoff, freq=f'{minutes}min'):
        end = start + pd.Timedelta(minutes=minutes)
        if end > cutoff:
            continue
        part = bars.loc[(bars.bar_start >= start) & (bars.bar_start < end)]
        expected = pd.date_range(start, periods=minutes, freq='min')
        if list(part.bar_start) != list(expected):
            continue
        result.append(dict(start=start, end=end, open=part.iloc[0].open,
                           high=part.high.max(), low=part.low.min(), close=part.iloc[-1].close,
                           volume=part.volume.sum()))
    return result


def build_features(package, session_bars, previous_session):
    cutoff = pd.Timestamp(package['cutoff'])
    bars = session_bars.loc[session_bars.bar_end <= cutoff].sort_values('bar_start').copy()
    opening, closing = bars.iloc[0][['session_open', 'session_close']]
    expected = pd.date_range(opening, cutoff - pd.Timedelta(minutes=1), freq='min')
    if list(bars.bar_start) != list(expected):
        raise ValueError('Require complete session prefix; no filled or compressed minutes')
    if len(bars) < 120 or cutoff + pd.Timedelta(minutes=5) > closing:
        raise ValueError('Ineligible 120-minute / five-minute origin')
    frozen = pd.DataFrame(package['kronos_inputs']['candles'])
    if list(pd.to_datetime(frozen.bar_start, utc=True)) != list(bars.tail(120).bar_start):
        raise ValueError('Frozen input window differs')
    cols = ['open','high','low','close','volume']
    if not np.array_equal(frozen[cols].to_numpy(float), bars.tail(120)[cols].to_numpy(float)):
        raise ValueError('Frozen prices differ')
    if previous_session.empty or previous_session.bar_end.max() >= opening:
        raise ValueError('Previous session must precede current session')
    prev_open, prev_close = previous_session.iloc[0][['session_open','session_close']]
    if list(previous_session.bar_start) != list(pd.date_range(prev_open, prev_close-pd.Timedelta(minutes=1), freq='min')):
        raise ValueError('Incomplete previous session')
    c = float(bars.iloc[-1].close)
    close = bars.close.to_numpy(float)
    tr = np.maximum.reduce([bars.high.to_numpy()-bars.low.to_numpy(),
                           np.abs(bars.high.to_numpy()-np.r_[close[0],close[:-1]]),
                           np.abs(bars.low.to_numpy()-np.r_[close[0],close[:-1]])])
    tr[0] = bars.iloc[0].high-bars.iloc[0].low
    atr = float(tr[:14].mean())
    for x in tr[14:]: atr = (13*atr+x)/14
    if not np.isfinite(atr) or atr <= 0:
        raise ValueError('Degenerate ATR')
    ret = np.diff(np.log(close))
    sma20, sma50 = close[-20:].mean(), close[-50:].mean()
    sd = close[-20:].std(ddof=1)
    f = dict(tod_frac_session=(cutoff-opening)/(closing-opening),
             is_near_close=float((closing-cutoff).total_seconds()<=1800),
             is_half_day=float((closing-opening).total_seconds()<390*60),
             dow_ny=float(cutoff.tz_convert('America/New_York').dayofweek+1),
             ret_1m=ret[-1], ret_5m_sum=ret[-5:].sum(), range_1m_atr=tr[-1]/atr,
             dist_prev_high_atr=(c-previous_session.high.max())/atr,
             dist_prev_low_atr=(c-previous_session.low.min())/atr,
             dist_prev_close_atr=(c-previous_session.iloc[-1].close)/atr,
             prev_session_range_atr=(previous_session.high.max()-previous_session.low.min())/atr,
             dist_sma20_atr=(c-sma20)/atr,dist_sma50_atr=(c-sma50)/atr,
             sma20_slope_atr=(sma20-close[-25:-5].mean())/atr,
             sma50_slope_atr=(sma50-close[-60:-10].mean())/atr,
             bb_pctb=(c-(sma20-2*sd))/(4*sd) if sd>0 else np.nan,
             bb_width_atr=4*sd/atr,atr14_over_close=atr/c,
             rvol_20=np.sqrt(np.square(ret[-20:]).sum()),
             nasdaq_vol_ratio_20=bars.iloc[-1].volume/bars.volume.tail(20).median(),
             nasdaq_vol_ratio_5_20=bars.volume.tail(5).sum()/(5*bars.volume.tail(20).median()))
    f['range_1m_atr'] = (bars.iloc[-1].high-bars.iloc[-1].low)/atr
    for minutes, prefix in [(5,'m5'),(60,'h60')]:
        agg = aggregate_completed(bars, opening, cutoff, minutes)
        last = agg[-1]
        f[prefix+'_ret_last'] = np.log(last['close']/last['open'])
        f[prefix+'_range_atr'] = (last['high']-last['low'])/atr
        if minutes == 5:
            width = last['high']-last['low']
            f['m5_clv'] = (2*last['close']-last['low']-last['high'])/width if width else np.nan
            f['m5_ret_prev'] = np.log(agg[-2]['close']/agg[-2]['open'])
    paths = np.asarray(package['forecast']['sampled_paths'])[:,: ,3]
    median = np.median(paths,axis=0)
    for i in range(5): f[f'k_d{i+1}_atr'] = (median[i]-c)/atr
    f['k_path_iqr5_atr'] = (np.quantile(paths[:,4],.75)-np.quantile(paths[:,4],.25))/atr
    f['k_path_frac_up5'] = np.mean(paths[:,4]>c)
    trade_names = ['ts_n_1m','ts_vwap_dist_atr_1m','ts_known_signed_fraction_1m',
                   'ts_unknown_share_1m','ts_vwap_dist_atr_5m',
                   'ts_known_signed_fraction_5m','ts_unknown_share_5m']
    f.update({name:np.nan for name in trade_names})
    ts = package['companion_inputs']['trade_minutes'][-5:]
    trade_ok = len(ts)==5 and all(r['status']=='valid' for r in ts)
    if trade_ok:
        if list(pd.to_datetime([r['bar_start'] for r in ts], utc=True)) != list(pd.to_datetime(frozen.bar_start.tail(5), utc=True)):
            raise ValueError('Trade feature timestamps differ')
        t = [r['features'] for r in ts]
        vols = frozen.volume.to_numpy(float)[-5:]
        prices = frozen.close.to_numpy(float)[-5:]
        vwaps = prices*(1+np.array([r['vwap_close_bps'] for r in t])/1e4)
        f.update(ts_n_1m=t[-1]['trade_count'],ts_vwap_dist_atr_1m=(vwaps[-1]-c)/atr,
                 ts_known_signed_fraction_1m=t[-1]['known_signed_fraction'],
                 ts_unknown_share_1m=t[-1]['unknown_fraction'],
                 ts_vwap_dist_atr_5m=(np.average(vwaps,weights=vols)-c)/atr,
                 ts_known_signed_fraction_5m=np.average([r['known_signed_fraction'] for r in t],weights=vols),
                 ts_unknown_share_5m=np.average([r['unknown_fraction'] for r in t],weights=vols))
    return {'origin_id':package['package_id'], 'feature_spec_version':'0.2',
            'forecast_time_utc':cutoff.isoformat(), 'ts_block_available':trade_ok,
            'candle_features_complete':all(np.isfinite(v) for k,v in f.items() if not k.startswith('ts_')),
            **{k:float(v) for k,v in f.items()}}
