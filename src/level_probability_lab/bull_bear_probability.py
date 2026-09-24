"""Multiclass scores from archived sampled OHLC paths.

Only engines with stored paths are scored as distributions. Binary-up fields
from the older ledger are intentionally not relabeled as three-class values.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from .bull_bear_truth import SPEC


def path_distribution(paths, origin, threshold=.001, horizon_index=4):
    values = np.asarray(paths, dtype=float)[:, horizon_index, 3]
    ret = values / float(origin) - 1.0
    return np.array([(ret > threshold).mean(), ((abs(ret) <= threshold)).mean(),
                     (ret < -threshold).mean()], dtype=float)


def multiclass_scores(y, p):
    losses = multiclass_losses(y, p)
    return tuple(float(v) for v in losses.mean(axis=0))


def multiclass_losses(y, p):
    y = np.asarray(y, dtype=int); p = np.asarray(p, dtype=float)
    if p.shape != (len(y), 3) or not np.isfinite(p).all() or (p < 0).any() or (p > 1).any() or not np.allclose(p.sum(axis=1), 1):
        raise ValueError('Invalid distribution')
    brier = np.sum((p - np.eye(3)[y]) ** 2, axis=1)
    clipped = np.clip(p, 1e-6, 1 - 1e-6)
    clipped /= clipped.sum(axis=1, keepdims=True)
    return np.column_stack((brier, -np.log(clipped[np.arange(len(y)), y])))


def paired_session_bootstrap(session_dates, differences, replicates=5000, seed=20260923):
    """Resample whole paired sessions; estimand is pooled per-origin loss delta."""
    table = pd.DataFrame(np.asarray(differences), columns=['brier', 'log_loss'])
    table['session'] = list(session_dates)
    grouped = table.groupby('session', sort=True)
    sums = grouped[['brier', 'log_loss']].sum().to_numpy()
    counts = grouped.size().to_numpy()
    delta = sums.sum(axis=0) / counts.sum()
    ci = [[None, None], [None, None]]
    if len(counts) >= 2:
        indices = np.random.default_rng(seed).integers(0, len(counts), (replicates, len(counts)))
        samples = sums[indices].sum(axis=1) / counts[indices].sum(axis=1)[:, None]
        ci = np.quantile(samples, [.025, .975], axis=0).T.tolist()
    return dict(n=int(counts.sum()), sessions=len(counts),
                brier_delta=float(delta[0]), brier_delta_ci95=ci[0],
                log_loss_delta=float(delta[1]), log_loss_delta_ci95=ci[1])


def _session_intervals(group, factory):
    values = []
    for _, session in group.groupby("session_date"):
        y = np.asarray(session.y, dtype=int)
        p = factory(session)
        values.append(multiclass_scores(y, p))
    if len(values) < 2:
        return [None, None], [None, None]
    values = np.asarray(values, dtype=float)
    return (np.quantile(values[:, 0], [.025, .975]).tolist(),
            np.quantile(values[:, 1], [.025, .975]).tolist())


def run(forecast_root, scores_path, output):
    scores = pd.read_parquet(scores_path)
    scores = scores.loc[scores.horizon_minutes == 5].copy()
    by_key = {(str(r.origin_timestamp), r.engine): r for r in scores.itertuples()}
    records = []
    for path in Path(forecast_root).glob('*/forecasts.jsonl'):
        for line in path.open(encoding='utf-8'):
            row = json.loads(line)
            model = 'kronos-small' if 'Kronos-small' in row['model_name'] else 'kronos-mini' if 'Kronos-mini' in row['model_name'] else None
            if not model: continue
            key = (row['last_input_timestamp'], model)
            actual = by_key.get(key)
            if actual is None: continue
            p = path_distribution(row['sampled_paths'], actual.origin_close)
            yret = actual.actual_close / actual.origin_close - 1
            y = 0 if yret > .001 else 2 if yret < -.001 else 1
            records.append(dict(engine=model, session_date=str(actual.session_date), origin=str(actual.origin_timestamp), y=y, p=p.tolist()))
    frame = pd.DataFrame(records)
    rows=[]
    for engine,g in frame.groupby('engine'):
        y=np.asarray(g.y.tolist());p=np.asarray(g.p.tolist());brier,logloss=multiclass_scores(y,p)
        session=[]
        for d,h in g.groupby('session_date'):
            session.append(multiclass_scores(np.asarray(h.y),np.asarray(h.p.tolist())))
        rows.append(dict(engine=engine,n=len(g),sessions=g.session_date.nunique(),brier=brier,log_loss=logloss,
                         session_brier_percentiles_2_5_97_5=[float(x) for x in np.quantile(np.asarray(session)[:,0],[.025,.975])] if len(session)>1 else [None,None],
                         class_prevalence=np.bincount(y,minlength=3).tolist(),probability_semantics='empirical path frequency; not calibrated'))
    result=dict(schema_version='qqq_bull_bear_probability_v1',label_spec=SPEC,classes=['bull','neutral','bear'],
                threshold=.001,horizon_minutes=5,rows=rows,raw_records=len(frame))
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2),encoding='utf-8');return result


def run_baseline_study(study_root, output):
    """Score the frozen May/June baseline-study sampled paths.

    This reader uses only the study's existing horizon-5 rows and forecast
    files; it does not regenerate forecasts or read the sealed July holdout.
    """
    root = Path(study_root)
    scores = pd.read_csv(root / "scores.csv")
    scores = scores.loc[scores.horizon == 5].copy()
    by_key = {(str(r.origin), r.model): r for r in scores.itertuples()}
    records = []
    for model in ("base", "small"):
        for path in (root / "forecasts" / model).glob("*.json"):
            row = json.loads(path.read_text(encoding="utf-8"))
            actual = by_key.get((str(row["origin"]), model))
            if actual is None:
                continue
            p = path_distribution(row["sampled_ohlc"], row["origin_close"])
            y = 0 if actual.actual > row["origin_close"] * 1.001 else 2 if actual.actual < row["origin_close"] * .999 else 1
            records.append(dict(engine=f"kronos-{model}", split=actual.split,
                                session_date=str(actual.date), origin=str(row["origin"]), y=y, p=p.tolist()))
    frame = pd.DataFrame(records)
    if frame.empty or frame.duplicated(['engine', 'origin']).any():
        raise ValueError('Missing or duplicate forecasts')
    a = frame[frame.engine == 'kronos-base'].set_index('origin').sort_index()
    b = frame[frame.engine == 'kronos-small'].set_index('origin').sort_index()
    if not a[['y', 'split', 'session_date']].equals(b[['y', 'split', 'session_date']]):
        raise ValueError('Engines must have identical origins and outcomes')
    rows = []
    reference = frame.drop_duplicates("origin")
    development = reference.loc[reference.split == "development"]
    climatology = (np.bincount(np.asarray(development.y, dtype=int), minlength=3) /
                   max(1, len(development))).astype(float)
    baseline_specs = {
        "persistence-neutral": lambda session: np.tile([0.0, 1.0, 0.0], (len(session), 1)),
        "development-climatology": lambda session: np.tile(climatology, (len(session), 1)),
    }
    for split, group in reference.groupby("split"):
        y = np.asarray(group.y, dtype=int)
        for engine, factory in baseline_specs.items():
            p = factory(group); brier, logloss = multiclass_scores(y, p)
            brier_ci, logloss_ci = _session_intervals(group, factory)
            rows.append(dict(engine=engine, split=split, n=len(group),
                             sessions=int(group.session_date.nunique()), brier=brier,
                             log_loss=logloss, class_prevalence=np.bincount(y, minlength=3).tolist(),
                             session_brier_percentiles_2_5_97_5=brier_ci, session_log_loss_percentiles_2_5_97_5=logloss_ci,
                             probability_semantics="fixed reference distribution"))
    for (engine, split), group in frame.groupby(["engine", "split"]):
        y = np.asarray(group.y, dtype=int); p = np.asarray(group.p.tolist(), dtype=float)
        brier, logloss = multiclass_scores(y, p)
        brier_ci, logloss_ci = _session_intervals(group, lambda session: np.asarray(session.p.tolist(), dtype=float))
        rows.append(dict(engine=engine, split=split, n=len(group), sessions=int(group.session_date.nunique()),
                         brier=brier, log_loss=logloss,
                         session_brier_percentiles_2_5_97_5=brier_ci, session_log_loss_percentiles_2_5_97_5=logloss_ci,
                         class_prevalence=np.bincount(y, minlength=3).tolist(),
                         probability_semantics="empirical path frequency; not calibrated"))
    comparisons = []
    for (engine, split), group in frame.groupby(['engine', 'split']):
        group = group.sort_values('origin')
        losses = multiclass_losses(group.y, np.asarray(group.p.tolist()))
        for baseline, factory in baseline_specs.items():
            delta = losses - multiclass_losses(group.y, factory(group))
            comparisons.append(dict(engine=engine, baseline=baseline, split=split,
                **paired_session_bootstrap(group.session_date, delta)))
    result = dict(schema_version="qqq_bull_bear_probability_v2", label_spec=SPEC,
                  comparisons=comparisons, bootstrap=dict(replicates=5000, seed=20260923,
                  method='paired session percentile bootstrap; pooled per-origin delta; negative favors engine'),
                  log_loss_epsilon=1e-6, development_climatology=climatology.tolist(),
                  classes=["bull", "neutral", "bear"], threshold=.001,
                  horizon_minutes=5, rows=rows, raw_records=len(frame),
                  source="kronos_baseline_v1", july_read=False)
    out = Path(output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
