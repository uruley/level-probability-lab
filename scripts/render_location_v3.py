"""Readable tables from the frozen August result, without selecting a rule."""
import json
import pandas as pd
from level_probability_lab.lab import ROOT
from level_probability_lab.location_evaluation import interval
from level_probability_lab.location_bands import FAMILIES, BANDS

OUT=ROOT/'data/location_evaluation_v3_august'


def pct(value): return '—' if value is None else f'{100*value:.1f}%'


def excess(value):
    if value['value'] is None: return '—'
    ci=value['ci95']; text=f"{100*value['value']:+.1f} pp"
    return text+(' (interval unavailable)' if ci is None else f' [{100*ci[0]:+.1f}, {100*ci[1]:+.1f}]')


def main():
    report=json.loads((OUT/'report.json').read_text()); df=pd.read_csv(OUT/'outcomes.csv')
    lines=['# August location replication — v3', '',
        '1,134 frozen Kronos Base forecasts across all 21 August 2026 regular sessions. '
        'This is additional development evidence: August had already been inspected. '
        'It is not an untouched final test.', '',
        '## Findings', '',
        '- Overall five-minute 1:1: 521/1,134 target-first (45.9%) versus 43.8% '
        'matched coin. Excess +2.2 percentage points, 95% session interval '
        '[-0.5, +4.8]; no clear overall advantage.',
        '- Hourly SMA distance >0.5–1R: 49/86 target-first (57.0%), versus '
        '45.9% coin, across 18 sessions. Excess +11.0 points [1.1, 20.0]. '
        'This is an exploratory positive signal, not a stable filter: May was '
        '40.6%, June 46.2%, and the August excess difference versus >2R still '
        'includes zero [-0.3, 19.0].',
        '- Strict confluence remains sparse: 2/8 (25.0%) in August versus '
        '4/5 (80.0%) in May/June. Broader >0.5–1R confluence has an exploratory '
        'positive excess but only 15 origins across six sessions, below the '
        'cross-month coverage requirement. Neither supports promotion.',
        '- The earlier negative >1–2R hourly-SMA association did not repeat '
        'clearly in August. No August origins were within 2R of daily Bollinger '
        'boundaries, so those near bands received no additional evidence.',
        '- Extended 2:1 shows a secondary overall excess of +2.7 points '
        '[0.1, 5.4]. This is among many secondary comparisons, not confirmation '
        'of a location effect or trading profitability.', '',
        'Keep these categories fixed. Preserve the hourly >0.5–1R observation '
        'as a candidate for future chronological confirmation; do not widen '
        'thresholds or turn the best August cell into a Scout rule. The next '
        'confirmatory period requires a prior-exposure audit and a frozen '
        'protocol before inspecting outcomes.', '',
        'Same model, 120-bar inputs, 25 paths, seed 42, five-minute forecast cadence, '
        'indicators, ATR14 risk, distance bands, and target/stop scoring as May/June. '
        'Forecast cutoffs run from 11:30 a.m. through 3:55 p.m. New York time, '
        'after the initial 120-minute lookback; this does not test the opening two hours. '
        'No training, data purchase, or changes to the replay. July forecast and '
        'outcome archives were not evaluated; completed July candles supply past '
        'indicator warmup only.', '',
        '## Overall August outcomes', '',
        'Percentages use all completed setups, including neither/expired and '
        'same-minute ambiguous outcomes. Fair coin chooses up/down with equal '
        'probability at the exact same origin, risk, ratio and deadline; its '
        'target-first rate is not assumed to be 50%.', '',
        '| Window | Reward:risk | Complete | Target first | Stop first | Neither/expired | Ambiguous | Matched coin | Kronos minus coin (95% session interval) |',
        '|---|---|---:|---:|---:|---:|---:|---:|---|']
    overall=[]
    for h in [5,60]:
        for ratio in [1,2,3]:
            block=df.loc[(df.horizon==h)&(df.ratio==ratio)].copy()
            valid=block.loc[block.kronos_status=='complete']; n=len(valid)
            paired=block.loc[(block.kronos_status=='complete')&(block.always_up_status=='complete')&(block.always_down_status=='complete')].copy()
            paired['denom']=1
            paired['coin']=.5*((paired.always_up_outcome=='target_first').astype(int)+(paired.always_down_outcome=='target_first').astype(int))
            paired['delta']=(paired.kronos_outcome=='target_first').astype(int)-paired.coin
            ci=interval(paired,'delta','denom',dates=block.date.unique())
            counts=valid.kronos_outcome.value_counts().to_dict()
            def fraction(name): return f"{pct(counts.get(name,0)/n)} ({counts.get(name,0)})" if n else '—'
            lines.append(f"| {'5 minutes' if h==5 else 'Up to 60/session close'} | {ratio}:1 | {n} | {fraction('target_first')} | {fraction('stop_first')} | {fraction('neither' if h==5 else 'expired')} | {fraction('ambiguous')} | {pct(float(paired.coin.mean()))} | {excess(ci)} |")
            overall.append(dict(horizon=h,ratio=ratio,complete=n,counts=counts,coin_rate=float(paired.coin.mean()),excess_vs_coin=ci))
    lines += ['', '## Primary view: five-minute 1:1 by location', '',
        'Distances use the original frozen one-minute ATR14 (R). “Near” does not '
        'change the Kronos inputs. The same forecast can appear in different '
        'families; bands within each family are disjoint. Empty groups remain visible.', '',
        '| Family | Distance | August origins / sessions | May/June target rate | August target rate | August coin | August excess (95% interval) |',
        '|---|---|---:|---:|---:|---:|---|']
    labels=dict(zip(BANDS,['≤0.5R','>0.5–1R','>1–2R','>2R','Unknown']))
    for family in FAMILIES:
        for band in BANDS:
            row=next(r for r in report['results'] if (r['horizon'],r['ratio'],r['family'],r['band'])==(5,1,family,band))
            old=next(r for r in report['reference_results'] if (r['period'],r['horizon'],r['ratio'],r['family'],r['band'])==('pooled',5,1,family,band))
            lines.append(f"| {family.replace('_',' ')} | {labels[band]} | {row['origins']} / {row['sessions']} | {pct(old['target_rate']['value'])} | {pct(row['target_rate']['value'])} | {pct(row['coin_rate'])} | {excess(row['excess_vs_coin'])} |")
    lines += ['', '## Primary near-versus-far comparisons', '',
        'Each band is compared with >2R within the same family. Excess difference '
        'subtracts each group’s matched coin result before comparing groups.', '',
        '| Family | Band vs >2R | Raw target-rate difference (95% interval) | Difference in excess over coin (95% interval) |',
        '|---|---|---|---|']
    for row in report['comparisons']:
        if row['horizon']==5 and row['ratio']==1:
            lines.append(f"| {row['family'].replace('_',' ')} | {labels[row['band']]} | {excess(row['raw_difference'])} | {excess(row['excess_difference'])} |")
    checks=json.loads((OUT/'independent_verification.json').read_text())
    lines += ['', '## Interpretation and integrity', '',
        'Intervals resample all 21 sessions, keeping overlapping origins together, '
        'with 2,000 draws and seed 20260919. Sparse groups can have no interval. '
        'All intervals are exploratory and unadjusted for multiple comparisons; '
        'isolated positive cells do not establish a reliable location filter. '
        'Raw counts and the unchanged cross-month support criterion are in coverage.json.', '',
        'These are associations and historical first-touch measurements, not explanations '
        'of internal model reasoning, executable fills, or returns. Hourly/daily '
        'indicators use completed regular-session buckets and Nasdaq-only data. '
        'Scout has not been retrained or promoted.', '',
        'Verification: 17 focused tests passed; all 1,134 forecast and context identities '
        f"were checked; {checks['independent_touch_checks']:,} independent target/stop "
        f"checks and {checks['summary_rows']} summary rows reconciled. No missing "
        'Kronos outcome rows. Original May/June files remain unchanged.', '',
        'Artifacts: frozen_config.json and protocol.md; immutable forecasts/base; '
        'prediction_contexts.jsonl; classifications.csv and coverage.json saved before '
        'outcomes; outcomes.csv; report.json; summary.csv; comparisons.csv; '
        'verification.json and independent_verification.json; manifest.json.', '']
    # Tables are generated separately from the frozen scoring implementation.
    (OUT/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    (OUT/'overall.json').write_text(json.dumps(overall,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__': main()
