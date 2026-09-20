"""Offline checks for replay isolation, frozen forecasts, gaps, and HTTP access."""
import json
from http.server import ThreadingHTTPServer
import threading
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

import numpy as np
import pandas as pd
import pytest

from conftest import make_session_frame
from level_probability_lab.exceptions import SessionBoundaryError
from level_probability_lab.lab import Lab, ReplaySession, make_handler


class RecordingModel:
    model_name = "test-base"

    def __init__(self):
        self.windows = []

    def forecast_paths(self, window, targets, sample_count, seed):
        self.windows.append(window.copy())
        assert window.bar_start.max() < min(targets)
        price = float(window.iloc[-1].close)
        return np.tile([price, price+.1, price-.1, price], (sample_count, 5, 1)), .01


@pytest.fixture
def setup_lab(tmp_path):
    lab = Lab(source=tmp_path / "unused.parquet", output=tmp_path)
    model = RecordingModel()
    lab.get_model = lambda key: model
    bars = make_session_frame(n=80)
    session = ReplaySession(bars, "2024-07-01", 60)
    return lab, model, session


def test_future_hidden_until_reveal_and_forecast_frozen(setup_lab):
    lab, model, session = setup_lab
    initial = session.state()
    assert len(initial["bars"]) == 60
    response = lab.predict(session, "base", 10)
    f = response["forecasts"][0]
    assert f["actual"] == [None]*5
    assert response["metrics"]["scored"] == 0
    assert len(model.windows[0]) == 60
    assert model.windows[0].bar_start.max() == session.bars.iloc[59].bar_start
    immutable = json.dumps(lab.store.all())
    advanced = session.advance(1)
    assert advanced["forecasts"][0]["actual"][0] == session.bars.iloc[60].close
    assert advanced["forecasts"][0]["actual"][1:] == [None]*4
    assert advanced["metrics"]["scored"] == 1
    assert json.dumps(lab.store.all()) == immutable
    assert session.advance(5)["metrics"]["scored"] == 5


def test_idempotence_and_restart_use_frozen_forecast(setup_lab):
    lab, model, session = setup_lab
    a = lab.predict(session, "base", 10)
    b = lab.predict(session, "base", 10)
    assert a["forecast_id"] == b["forecast_id"]
    assert len(model.windows) == 1
    assert len(lab.store.all()) == 1
    restarted = ReplaySession(session.bars, session.date, 60)
    c = lab.predict(restarted, "base", 10)
    assert c["forecasts"][0]["actual"] == [None]*5
    assert len(model.windows) == 1


def test_input_gaps_block_prediction(setup_lab):
    lab, model, session = setup_lab
    session.bars = session.bars.drop(index=30).reset_index(drop=True)
    assert not session.state()["can_forecast"]
    with pytest.raises(SessionBoundaryError):
        lab.predict(session, "base", 10)
    assert not model.windows


def test_missing_outcome_is_not_filled_or_scored(setup_lab):
    lab, _, session = setup_lab
    session.bars = session.bars.drop(index=61).reset_index(drop=True)
    lab.predict(session, "base", 10)
    result = session.advance(5)
    assert result["forecasts"][0]["actual"][1] is None
    assert result["forecasts"][0]["outcome_status"][1] == "missing"
    assert result["metrics"]["scored"] == 4


def test_close_boundary_and_bad_arguments(setup_lab):
    lab, model, session = setup_lab
    session.cursor = len(session.bars)-4
    assert not session.state()["can_forecast"]
    with pytest.raises(SessionBoundaryError):
        lab.predict(session, "base", 10)
    with pytest.raises(ValueError):
        session.advance(-1)
    with pytest.raises(ValueError):
        lab.predict(session, "unrecognized", 10)
    assert not model.windows


def test_http_requires_local_host_and_token(setup_lab):
    lab, _, session = setup_lab
    lab.sessions["test"] = session
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(lab, "test-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = build_opener(ProxyHandler({}))
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as err:
            opener.open(Request(url+"/api/step", data=b'{"session_id":"test"}'))
        assert err.value.code == 403
        with pytest.raises(HTTPError) as err:
            opener.open(Request(url+"/", headers={"Host": "untrusted.example"}))
        assert err.value.code == 403
        request = Request(url+"/api/step", data=b'{"session_id":"test","count":1}',
                          headers={"X-Lab-Token": "test-token"})
        with opener.open(request) as response:
            data = json.load(response)
        assert len(data["bars"]) == 61
        with opener.open(url+"/vendor/lightweight-charts.js") as response:
            assert response.headers['Content-Type']=='text/javascript'
            assert b'LightweightCharts' in response.read()
        with opener.open(url+"/vendor/NOTICE-lightweight-charts") as response:
            assert b'TradingView' in response.read()
        with pytest.raises(HTTPError):
            opener.open(url+"/vendor/../lab.py")
    finally:
        server.shutdown()
        server.server_close()

def test_amount_modes_have_separate_frozen_records(setup_lab, monkeypatch):
    lab, model, session = setup_lab
    def attach(window, path):
        return window.assign(amount=window.volume * window.close * .99)
    monkeypatch.setattr('level_probability_lab.trade_amount.attach_amount', attach)
    a = lab.predict(session, 'base', 10)
    b = lab.predict(session, 'base', 10, 'trades')
    assert a['forecast_id'] != b['forecast_id']
    assert 'amount' not in model.windows[0]
    assert 'amount' in model.windows[1]
    assert len(model.windows[1]) == session.lookback
    lab.predict(session, 'base', 10, 'trades')
    assert len(model.windows) == 2
    assert all('amount' in row for row in lab.store.all()[1]['input_window'])
