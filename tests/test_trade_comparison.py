import json

import numpy as np
import pandas as pd
import pytest

from level_probability_lab import trade_comparison as tc


def fake_data():
    rng=np.random.default_rng(91)
    x=rng.normal(size=(40,18))
    trade=rng.normal(size=(40,24))
    base=np.full((40,5),100.)
    return dict(candle=x,trade=trade,base=base,small=base.copy(),
        actual=base+x[:,0,None]*.1+trade[:,0,None]*.02,
        origin_close=np.full(40,100.),split=np.array(["development"]*20+["validation"]*20),
        dates=np.array([f"day{i//4}" for i in range(40)]))


def test_scalers_and_coefficients_fit_only_may():
    data=fake_data()
    models,_=tc.choose_models(data)
    for name,model in models.items():
        x=data["candle"] if name=="candle_control" else np.column_stack([data["candle"],data["trade"]])
        np.testing.assert_allclose(model["mean"],x[:20].mean(axis=0))
        y=(data["actual"]-data["base"])/data["origin_close"][:,None]*1e4
        independent=tc.fit_ridge(x[:20],y[:20],model["alpha"])
        np.testing.assert_allclose(model["coef"],independent["coef"])
    # A validation-only shift may select a different penalty, never enters scaler.
    data["candle"][20:]+=10000
    shifted,_=tc.choose_models(data)
    np.testing.assert_allclose(shifted["candle_control"]["mean"],models["candle_control"]["mean"])


def test_holdout_gate_runs_before_any_july_read(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail("Read attempted before freeze")
    monkeypatch.setattr(tc,"load_minutes",forbidden)
    monkeypatch.setattr(tc,"load_day",forbidden)
    with pytest.raises(ValueError,match="frozen model"):
        tc.evaluate_holdout(tmp_path,tmp_path/"july.parquet",tmp_path/"gate.json")


def test_fit_rejects_july_origins_before_read(tmp_path,monkeypatch):
    (tmp_path/"progress.json").write_text(json.dumps({"status":"complete"}))
    (tmp_path/"origins.json").write_text(json.dumps([{"date":"2026-07-01"}]))
    monkeypatch.setattr(tc,"require_gate",lambda *args:None)
    monkeypatch.setattr(tc,"load_minutes",lambda *args:pytest.fail("July read"))
    with pytest.raises(ValueError,match="holdout"):
        tc.fit_study(tmp_path,tmp_path/"features",tmp_path/"gate",tmp_path/"out")


def test_direction_neutral_and_negative_lift_are_reported():
    data=dict(actual=np.full((4,5),101.),origin_close=np.full(4,100.),dates=np.array(["a","a","b","b"]))
    arms=dict(persistence=np.full((4,5),100.),candle_control=np.full((4,5),100.9),trade_augmented=np.full((4,5),99.))
    report=tc.evaluate_predictions(data,arms)
    assert report["metrics"][0]["direction_n"]==0
    assert report["metrics"][0]["direction_accuracy"] is None
    assert report["primary"]["relative_mae_improvement"]<0
    assert not report["primary"]["practical_threshold_met"]
    assert report["primary"]["ci95"][0]>0


def test_trade_windows_require_every_minute_and_quality():
    index=pd.date_range("2026-05-01T15:15Z",periods=15,freq="min")
    frame=pd.DataFrame(1.,index=index,columns=tc.TRADE_FIELDS)
    frame["feature_eligible"]=True
    frame["reconciled"]=True
    frame["available_at"]=index+pd.Timedelta(minutes=1)
    np.testing.assert_allclose(tc.trailing_trade_features(frame,index[-1]),np.ones(24))
    with pytest.raises(ValueError,match="Missing"):
        tc.trailing_trade_features(frame.drop(index[3]),index[-1])
    frame.loc[index[3],"feature_eligible"]=False
    with pytest.raises(ValueError,match="quality"):
        tc.trailing_trade_features(frame,index[-1])


def test_matched_origins_no_silent_imputation(tmp_path,monkeypatch):
    index=pd.date_range("2026-05-01T13:30Z",periods=140,freq="min")
    day=pd.DataFrame(dict(bar_start=index,open=100.,high=101.,low=99.,close=100.,volume=10.,
        session_open=index[0],session_close=index[0]+pd.Timedelta(minutes=390)))
    monkeypatch.setattr(tc,"load_day",lambda *args:day)
    features=pd.DataFrame(1.,index=index,columns=tc.TRADE_FIELDS)
    features["feature_eligible"]=True
    features["reconciled"]=True
    features["available_at"]=index+pd.Timedelta(minutes=1)
    origins=[dict(date="2026-05-01",split="development",origin=index[n].isoformat()) for n in (119,124)]
    features.loc[index[105],"feature_eligible"]=False
    t=index[124]
    window=day.iloc[5:125].reset_index(drop=True)
    targets=pd.date_range(t+pd.Timedelta(minutes=1),periods=5,freq="min")
    for model in ("base","small"):
        record={**origins[1],"model":model,"origin_close":100.,"sampled_ohlc":np.full((25,5,4),100.).tolist(),
            "input_sha256":tc.hashlib.sha256(window[["bar_start","open","high","low","close","volume"]].to_csv(index=False).encode()).hexdigest(),
            "targets":[x.isoformat() for x in targets]}
        tc.write_json(tc.forecast_file(tmp_path,model,t),record,True)
    data,excluded=tc.assemble(origins,tmp_path,features,tmp_path/"unused")
    assert data["origins"].tolist()==[origins[1]["origin"]]
    assert len(data["base"])==len(data["small"])==len(data["trade"])==1
    assert excluded[0]["origin"]==origins[0]["origin"]


def test_single_session_has_no_spurious_confidence():
    result=tc.paired_comparison(["a","a"],[0.,0.],[1.,1.])
    assert result["ci95"] is None
    assert not result["practical_threshold_met"]


def test_fit_feature_read_ends_before_july(monkeypatch):
    calls=[]
    def read(path,filters):
        calls.append(filters)
        return pd.DataFrame({"bar_start":pd.to_datetime(["2026-06-30T19:59Z"])})
    monkeypatch.setattr(pd,"read_parquet",read)
    tc.load_minutes("unused")
    assert calls==[[('bar_start','>=',pd.Timestamp('2026-05-01',tz='UTC')),
                    ('bar_start','<',pd.Timestamp('2026-07-01',tz='UTC'))]]


def test_coefficients_seal_detects_changes(tmp_path):
    frozen=tmp_path/"frozen_model.json"
    tc.write_json(frozen,{"hashes":{},"models":{"coef":1}},True)
    tc.write_json(tmp_path/"frozen_model_sha256.json",{"sha256":tc.sha256(frozen)},True)
    assert tc.require_frozen(tmp_path)["models"]["coef"]==1
    frozen.write_text('{"hashes":{},"models":{"coef":2}}')
    with pytest.raises(ValueError,match="seal"):
        tc.require_frozen(tmp_path)


def test_prediction_csv_resume_requires_identical_content(tmp_path):
    data=dict(origins=np.array(["origin"]),dates=np.array(["date"]),split=np.array(["holdout"]),
              actual=np.ones((1,5)),origin_close=np.ones(1))
    path=tmp_path/"predictions.csv"
    tc.save_predictions(path,data,{"base":np.ones((1,5))})
    tc.save_predictions(path,data,{"base":np.ones((1,5))})
    with pytest.raises(ValueError,match="differ"):
        tc.save_predictions(path,data,{"base":np.zeros((1,5))})
