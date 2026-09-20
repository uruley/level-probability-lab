"""Frozen residual-ridge experiment; no July outcomes are read during fitting.

Models predict corrections to Base's median closes. Candle control and trade
augmentation use identical origins; scalers and coefficients use May only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .baseline_study import CONFIG, eligible_origins, forecast_file, write_json
from .lab import ROOT, BASE_REVISION, load_day
from .calendar import session_schedule

TRADE_FIELDS = ("trade_count", "mean_size", "max_size_fraction", "size_cv",
                "vwap_close_bps", "within_minute_realized_var", "known_signed_fraction", "unknown_fraction")
CANDLE_FIELDS = ([f"log_return_{n}" for n in (1, 5, 15, 60, 120)]
    + ["return_std_15", "return_std_60", "range_mean_15", "range_mean_60",
       "log_last_volume", "volume_ratio_15", "tod_sin", "tod_cos"]
    + [f"kronos_return_bps_{h}" for h in range(1, 6)])
TRADE_COLUMNS = [f"{field}_mean_{n}" for n in (1, 5, 15) for field in TRADE_FIELDS]
ALPHAS = (1., 10., 100.)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8*1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def candle_features(window, median):
    if len(window) != 120:
        raise ValueError("Require exactly120 completed candles")
    close = window.close.to_numpy(float)
    returns = np.diff(np.log(close))
    values = [np.log(close[-1]/close[-1-n]) for n in (1,5,15,60)]
    # Exact120-minute open-to-close span;120 closes contain only119 close returns.
    values.append(np.log(close[-1]/float(window.iloc[0].open)))
    values.extend(np.std(returns[-n:], ddof=1) for n in (15,60))
    values.extend(float((window.high-window.low).tail(n).mean()/close[-1]) for n in (15,60))
    values.extend([np.log1p(float(window.iloc[-1].volume)),
                   float(window.iloc[-1].volume/window.volume.tail(15).mean())])
    end = pd.Timestamp(window.iloc[-1].bar_start).tz_convert("America/New_York") + pd.Timedelta(minutes=1)
    opening=pd.Timestamp(window.iloc[-1].session_open)
    closing=pd.Timestamp(window.iloc[-1].session_close)
    phase = 2*np.pi*(end-opening).total_seconds()/(closing-opening).total_seconds()
    values.extend([np.sin(phase), np.cos(phase)])
    values.extend((np.asarray(median)/close[-1]-1)*1e4)
    result = np.asarray(values, float)
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite candle features")
    return result


def trailing_trade_features(minutes, origin):
    expected = pd.date_range(pd.Timestamp(origin)-pd.Timedelta(minutes=14), periods=15, freq="min")
    if not expected.isin(minutes.index).all():
        raise ValueError("Missing completed trade feature minute")
    window = minutes.loc[expected, list(TRADE_FIELDS)]
    quality=minutes.loc[expected]
    if not (quality.feature_eligible.eq(True)&quality.reconciled.eq(True)).all():
        raise ValueError("Trade feature window failed reconciliation/quality gate")
    if (pd.to_datetime(quality.available_at,utc=True)>pd.Timestamp(origin)+pd.Timedelta(minutes=1)).any():
        raise ValueError("Trade features unavailable at forecast time")
    values = np.concatenate([window.tail(n).mean(axis=0, skipna=False).to_numpy(float) for n in (1,5,15)])
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite trade features; imputation forbidden")
    return values


def fit_ridge(x, y, alpha):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if not len(x) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Finite nonempty training data required")
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    z = (x-mean)/scale
    intercept = y.mean(axis=0)
    coef = np.linalg.solve(z.T@z+float(alpha)*np.eye(z.shape[1]), z.T@(y-intercept))
    return dict(alpha=float(alpha), mean=mean.tolist(), scale=scale.tolist(),
                intercept=intercept.tolist(), coef=coef.tolist())


def predict_ridge(model, x):
    return ((np.asarray(x)-model["mean"])/model["scale"])@np.asarray(model["coef"])+model["intercept"]


def paired_comparison(dates, candidate_error, control_error):
    frame = pd.DataFrame(dict(date=dates, delta=np.asarray(candidate_error)-control_error))
    grouped = frame.groupby("date").delta.agg(["sum", "count"])
    if not len(grouped):
        raise ValueError("No matched origins")
    mean_delta = float(frame.delta.mean())
    control_mae = float(np.mean(control_error))
    relative = -mean_delta/control_mae if control_mae > 0 else None
    ci = None
    if len(grouped) >= 2:
        rng = np.random.default_rng(20260919)
        ix = rng.integers(0,len(grouped),size=(2000,len(grouped)))
        draws = grouped["sum"].to_numpy()[ix].sum(axis=1)/grouped["count"].to_numpy()[ix].sum(axis=1)
        ci = np.quantile(draws,[.025,.975]).tolist()
    return dict(mae_difference=mean_delta, relative_mae_improvement=relative, ci95=ci,
                sessions=len(grouped), practical_threshold_met=bool(relative is not None and relative>=.01 and ci is not None and ci[1]<0))


def evaluate_predictions(data, arms):
    actual, origin = data["actual"], data["origin_close"]
    rows = []
    for name, predicted in arms.items():
        for h in range(5):
            error = predicted[:,h]-actual[:,h]
            p_sign, a_sign = np.sign(predicted[:,h]-origin), np.sign(actual[:,h]-origin)
            valid = (p_sign!=0)&(a_sign!=0)
            rows.append(dict(arm=name,horizon=h+1,n=len(error),mae=float(np.abs(error).mean()),
                rmse=float(np.sqrt(np.mean(error**2))),direction_n=int(valid.sum()),
                predicted_neutral_n=int((p_sign==0).sum()),actual_neutral_n=int((a_sign==0).sum()),
                direction_accuracy=float((p_sign[valid]==a_sign[valid]).mean()) if valid.any() else None))
    comparisons = [dict(horizon=h+1,**paired_comparison(data["dates"],
        np.abs(arms["trade_augmented"][:,h]-actual[:,h]),
        np.abs(arms["candle_control"][:,h]-actual[:,h]))) for h in range(5)]
    return dict(metrics=rows, trade_vs_candle=comparisons, primary=comparisons[4],
                note="Primary endpoint is h5 close MAE; intervals resample whole sessions. Direction conditional on both moves nonzero. No profitability claim.")


def choose_models(data):
    train = np.asarray(data["split"]) == "development"
    valid = np.asarray(data["split"]) == "validation"
    if not train.any() or not valid.any():
        raise ValueError("Both May development and June validation required")
    residual = (data["actual"]-data["base"])/data["origin_close"][:,None]*1e4
    selected, sweep = {}, {}
    for arm, features in (("candle_control", data["candle"]),
                          ("trade_augmented",np.column_stack([data["candle"],data["trade"]]))):
        options = []
        for alpha in ALPHAS:
            model = fit_ridge(features[train],residual[train],alpha)
            predicted = data["base"][valid]+predict_ridge(model,features[valid])*data["origin_close"][valid,None]/1e4
            mae = float(np.abs(predicted[:,4]-data["actual"][valid,4]).mean())
            options.append((mae,alpha,model))
        best = min(options,key=lambda item:(item[0],item[1]))
        selected[arm] = best[2]
        selected[arm]["features"] = CANDLE_FIELDS + (TRADE_COLUMNS if arm=="trade_augmented" else [])
        sweep[arm] = [dict(alpha=a,june_h5_mae=m) for m,a,_ in options]
    return selected,sweep


def predictions(data, models):
    arms = dict(raw_base=data["base"],raw_small=data["small"],
                persistence=np.repeat(data["origin_close"][:,None],5,axis=1))
    for arm in ("candle_control","trade_augmented"):
        x = data["candle"] if arm=="candle_control" else np.column_stack([data["candle"],data["trade"]])
        arms[arm] = data["base"]+predict_ridge(models[arm],x)*data["origin_close"][:,None]/1e4
    return arms


def load_minutes(path, holdout=False):
    start,end = ("2026-07-01","2026-08-01") if holdout else ("2026-05-01","2026-07-01")
    frame = pd.read_parquet(path, filters=[("bar_start",">=",pd.Timestamp(start,tz="UTC")),
                                          ("bar_start","<",pd.Timestamp(end,tz="UTC"))])
    frame["bar_start"] = pd.to_datetime(frame.bar_start,utc=True)
    if frame.bar_start.duplicated().any():
        raise ValueError("Duplicate trade feature minutes")
    return frame.set_index("bar_start").sort_index()


def assemble(origins, store, minutes, source):
    result = {k:[] for k in ("dates","split","origin_close","actual","base","small","candle","trade","origins")}
    excluded, days = [], {}
    for item in origins:
        date,t = item["date"],pd.Timestamp(item["origin"])
        if date not in days:
            days[date] = load_day(source,date).set_index("bar_start",drop=False)
        day = days[date]
        try:
            trade = trailing_trade_features(minutes,t)
        except ValueError as exc:
            excluded.append({**item,"reason":str(exc)})
            continue
        window = day.loc[t-pd.Timedelta(minutes=119):t]
        targets = pd.date_range(t+pd.Timedelta(minutes=1),periods=5,freq="min")
        origin = float(window.iloc[-1].close)
        medians = {}
        input_hash = hashlib.sha256(window.reset_index(drop=True)[["bar_start","open","high","low","close","volume"]].to_csv(index=False).encode()).hexdigest()
        for model in ("base","small"):
            record = json.loads(forecast_file(store,model,t).read_text())
            paths = np.asarray(record["sampled_ohlc"],float)
            if (record["origin"]!=item["origin"] or record["model"]!=model or
                record["input_sha256"]!=input_hash or record["origin_close"]!=origin or
                record["targets"]!=[x.isoformat() for x in targets] or
                paths.shape!=(25,5,4) or not np.isfinite(paths).all()):
                raise ValueError("Forecast identity/shape mismatch")
            medians[model] = np.median(paths[:,:,3],axis=0)
        values = dict(dates=date,split=item["split"],origin_close=origin,
            actual=day.loc[targets,"close"].to_numpy(float),base=medians["base"],small=medians["small"],
            candle=candle_features(window,medians["base"]),trade=trade,origins=item["origin"])
        for key,value in values.items():
            result[key].append(value)
    if not result["dates"]:
        raise ValueError("No matched eligible origins")
    return {k:np.asarray(v) for k,v in result.items()},excluded


def source_hashes(baseline, features, gate):
    paths = dict(baseline_config=baseline/"frozen_config.json",baseline_origins=baseline/"origins.json",
        features=features,gate=gate,runner=Path(__file__),
        candles=ROOT/CONFIG["source"],adapter=Path(__file__).parent/"ghost_candles/adapter.py",
        lab=Path(__file__).parent/"lab.py",trade_producer=Path(__file__).parent/"trade_features.py")
    for path in sorted((baseline/"forecasts").rglob("*.json")):
        paths["forecast:"+str(path.relative_to(baseline))]=path
    for path in sorted(Path(r"C:\Users\ruley\Kronos\model").rglob("*.py")):
        paths["kronos:"+str(path)]=path
    return {key:dict(path=str(path.resolve()),sha256=sha256(path)) for key,path in paths.items()}


def require_gate(gate, features):
    value = json.loads(Path(gate).read_text())
    if value.get("accepted") is not True:
        raise ValueError("Trade feature quality gate must be accepted before fitting")
    if value.get("features_sha256") != sha256(features):
        raise ValueError("Quality gate does not match trade feature file")
    return value


def fit_study(baseline, features, gate, output):
    if json.loads((baseline/"progress.json").read_text()).get("status")!="complete":
        raise ValueError("Baseline study must be complete")
    require_gate(gate,features)
    origins = json.loads((baseline/"origins.json").read_text())
    if any(not ("2026-05-01"<=i["date"]<"2026-07-01") for i in origins):
        raise ValueError("Fit input contains holdout/out-of-period origins")
    data,excluded = assemble(origins,baseline,load_minutes(features),ROOT/CONFIG["source"])
    models,sweep = choose_models(data)
    frozen = dict(version=1,primary_model="base",primary_horizon=5,alphas=list(ALPHAS),
        models=models,alpha_selection=sweep,hashes=source_hashes(baseline,features,gate),
        input_definition="120min return uses first open to last close; other returns use closes; no refit after June selection",
        excluded_origins=excluded,matched_origins=data["origins"].tolist(),july_read=False)
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/"frozen_model.json",frozen,True)
    write_json(output/"frozen_model_sha256.json",dict(sha256=sha256(output/"frozen_model.json")),True)
    arms=predictions(data,models)
    save_predictions(output/"development_validation_predictions.csv",data,arms)
    reports={}
    for split in ("development","validation"):
        mask=data["split"]==split
        reports[split]=evaluate_predictions({k:v[mask] for k,v in data.items()},{k:v[mask] for k,v in arms.items()})
    reports["note"]="June selects alpha; June results are selection-biased. Only subsequent frozen July evaluation tests the primary claim."
    write_json(output/"development_validation_report.json",reports,True)
    return frozen


def require_frozen(output):
    path=output/"frozen_model.json"
    if not path.exists():
        raise ValueError("Holdout blocked: frozen model must exist before July is read")
    seal=output/"frozen_model_sha256.json"
    if not seal.exists() or json.loads(seal.read_text())["sha256"]!=sha256(path):
        raise ValueError("Frozen coefficients/scalers seal mismatch")
    frozen=json.loads(path.read_text())
    for name,item in frozen["hashes"].items():
        if sha256(item["path"])!=item["sha256"]:
            raise ValueError(f"Frozen source changed: {name}")
    return frozen


def save_predictions(path,data,arms):
    rows=[]
    for arm,predicted in arms.items():
        for i,origin in enumerate(data["origins"]):
            for h in range(5):
                rows.append(dict(origin=origin,date=data["dates"][i],split=data["split"][i],arm=arm,horizon=h+1,
                    actual=float(data["actual"][i,h]),predicted=float(predicted[i,h]),
                    origin_close=float(data["origin_close"][i])))
    payload=pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
    path=Path(path)
    if path.exists():
        if path.read_bytes()!=payload:
            raise ValueError("Existing prediction rows differ; refusing overwrite")
        return
    temporary=path.with_suffix(path.suffix+".tmp")
    # A process lock serializes holdout writers; interrupted temporary bytes are disposable.
    with temporary.open("wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)


def _evaluate_holdout(output,features,gate):
    """Explicit final-test entrypoint. All frozen checks precede July reads."""
    frozen=require_frozen(output)
    require_gate(gate,features)
    if (output/"holdout_report.json").exists():
        raise ValueError("July already evaluated; refusing another final test")
    holdout=output/"holdout"
    holdout.mkdir(parents=True,exist_ok=True)
    manifest=dict(frozen_sha256=sha256(output/"frozen_model.json"),features_sha256=sha256(features),gate_sha256=sha256(gate))
    manifest_path=holdout/"manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text())!=manifest:
            raise ValueError("Holdout inputs changed during resumed evaluation")
    else:
        write_json(manifest_path,manifest,True)
    minutes=load_minutes(features,holdout=True)
    source=ROOT/CONFIG["source"]
    origins=[]
    days={}
    exclusions=[]
    for date,session in session_schedule("2026-07-01","2026-07-31").iterrows():
        date=str(date.date())
        try:
            bars=load_day(source,date)
        except ValueError as exc:
            exclusions.append(dict(date=date,reason=str(exc)))
            continue
        days[date]=bars.set_index("bar_start",drop=False)
        for t in eligible_origins(bars,session.market_open,session.market_close):
            item=dict(date=date,split="holdout",origin=t.isoformat())
            try:
                trailing_trade_features(minutes,t)
            except ValueError as exc:
                exclusions.append({**item,"reason":str(exc)})
                continue
            origins.append(item)
    if not origins:
        raise ValueError("No matched July origins; refusing evaluation")
    write_json(holdout/"eligibility.json",dict(origins=origins,excluded=exclusions))
    # Lazy import ensures preparation/fitting never loads a model or uses a GPU.
    from .ghost_candles.adapter import KronosPathForecaster
    import torch
    import gc
    completed=0
    start=time.monotonic()
    for model in ("base","small"):
        forecaster=None
        for item in origins:
            t=pd.Timestamp(item["origin"])
            window=days[item["date"]].loc[t-pd.Timedelta(minutes=119):t].reset_index(drop=True)
            targets=pd.date_range(t+pd.Timedelta(minutes=1),periods=5,freq="min")
            path=forecast_file(holdout,model,t)
            if path.exists():
                completed+=1
                continue  # Full identity validation in assemble before any score.
            if forecaster is None:
                kwargs=dict(model_id="NeoQuasar/Kronos-base",model_revision=BASE_REVISION,cache_dir=ROOT/"data/models/hub") if model=="base" else {}
                forecaster=KronosPathForecaster(**kwargs)
            paths,seconds=forecaster.forecast_paths(window,targets,25,42)
            if paths.shape!=(25,5,4) or not np.isfinite(paths).all():
                raise ValueError("Invalid heldout model paths")
            write_json(path,{**item,"model":model,"origin_close":float(window.iloc[-1].close),
                "input_sha256":hashlib.sha256(window[["bar_start","open","high","low","close","volume"]].to_csv(index=False).encode()).hexdigest(),
                "targets":[x.isoformat() for x in targets],"sampled_ohlc":paths.tolist(),"inference_seconds":seconds},True)
            completed+=1
            if completed%25==0:
                progress=dict(status="forecasting",model=model,completed=completed,total=2*len(origins),elapsed_seconds=round(time.monotonic()-start,1))
                write_json(holdout/"progress.json",progress)
                print(json.dumps(progress),flush=True)
        del forecaster
        gc.collect()
        torch.cuda.empty_cache()
    data,extra_exclusions=assemble(origins,holdout,minutes,source)
    arms=predictions(data,frozen["models"])
    report=evaluate_predictions(data,arms)
    report["excluded_origins"]=exclusions+extra_exclusions
    report["matched_origins"]=len(data["origins"])
    report["frozen_sha256"]=sha256(output/"frozen_model.json")
    report["interpretation"]=("Prespecified evidence threshold met" if report["primary"]["practical_threshold_met"] else
                              "This study did not establish incremental value; this does not prove no effect")
    save_predictions(output/"holdout_predictions.csv",data,arms)
    write_json(output/"holdout_report.json",report,True)
    write_json(holdout/"progress.json",dict(status="complete",completed=completed,total=2*len(origins)))
    return report


def evaluate_holdout(output,features,gate):
    # Require freeze before even creating a run marker; July data reads occur only inside.
    require_frozen(output)
    lock=output/"holdout.run.lock"
    with lock.open("x") as f:
        f.write(str(os.getpid()))
    try:
        return _evaluate_holdout(output,features,gate)
    finally:
        lock.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=ROOT/"data/kronos_baseline_v1")
    parser.add_argument("--features",type=Path,required=True)
    parser.add_argument("--gate",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=ROOT/"data/trade_comparison_v1")
    parser.add_argument("--evaluate-holdout",action="store_true",help="Explicitly unseal July after frozen model review")
    args=parser.parse_args()
    if args.evaluate_holdout:
        evaluate_holdout(args.output,args.features,args.gate)
    else:
        fit_study(args.baseline,args.features,args.gate,args.output)


if __name__=="__main__":
    main()
