"""Schema naming and finite spending guard regressions; all provider calls mocked."""
import pytest

from level_probability_lab.exceptions import DownloadBlocked
from level_probability_lab.providers.databento_adapter import DatabentoAdapter
from test_download_guard import REQUEST, FakeHistorical, _adapter


def test_trades_request_keeps_its_schema_in_artifact(tmp_path, monkeypatch):
    fake = FakeHistorical(cost=2.49)
    adapter = _adapter(tmp_path, fake, monkeypatch)
    result = adapter.download({**REQUEST, "schema": "trades", "symbols": ["QQQ"]},
        download_enabled=True, approved=True, spending_cap_usd=3)
    assert result["raw_path"].endswith(".trades.dbn.zst")
    assert fake.timeseries.calls[0]["schema"] == "trades"


def test_cli_trade_download_does_not_use_candle_decoder(tmp_path, monkeypatch):
    import json
    from level_probability_lab.cli import main
    from level_probability_lab.providers.databento_adapter import request_fingerprint
    request = {**REQUEST, "schema": "trades", "symbols": ["QQQ"]}
    quote = tmp_path / "quote.json"
    quote.write_text(json.dumps({"request": request, "fingerprint": request_fingerprint(request)}))
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "databento_pilot.yaml").write_text("databento:\n  download_enabled: false\n  spending_cap_usd: 0\n")
    def fake_download(*args, **kwargs):
        return {"state": "completed", "raw_path": str(tmp_path / "test.trades.dbn.zst")}
    def refuse_candle_decoder(*args, **kwargs):
        pytest.fail("trade data must not be interpreted as OHLCV")
    monkeypatch.setattr(DatabentoAdapter, "download", fake_download)
    monkeypatch.setattr("level_probability_lab.ingest.ohlcv_from_dbn_file", refuse_candle_decoder)
    assert main(["--project-root", str(tmp_path), "download", "--quote-manifest", str(quote),
                 "--enable-download", "--i-approve-this-exact-request", "--spending-cap", "3"]) == 0


@pytest.mark.parametrize("cap", [float("nan"), float("inf"), -1, 0])
def test_nonfinite_or_nonpositive_caps_never_request(tmp_path, monkeypatch, cap):
    fake = FakeHistorical()
    with pytest.raises(DownloadBlocked):
        _adapter(tmp_path, fake, monkeypatch).download(REQUEST,
            download_enabled=True, approved=True, spending_cap_usd=cap)
    assert not fake.timeseries.calls


@pytest.mark.parametrize("cost", [float("nan"), float("inf"), -1])
def test_invalid_quote_never_requests(tmp_path, monkeypatch, cost):
    fake = FakeHistorical(cost=cost)
    with pytest.raises(DownloadBlocked):
        _adapter(tmp_path, fake, monkeypatch).download(REQUEST,
            download_enabled=True, approved=True, spending_cap_usd=3)
    assert not fake.timeseries.calls
