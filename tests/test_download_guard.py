from __future__ import annotations

from types import SimpleNamespace

import pytest

from level_probability_lab.exceptions import CostCapExceeded, DownloadBlocked, MissingCredentialsError, UncertainChargeError
from level_probability_lab.providers.databento_adapter import DatabentoAdapter, canonical_request, request_fingerprint


REQUEST = {
    "dataset": "EQUS.MINI",
    "schema": "ohlcv-1m",
    "symbols": ["QQQ", "SPY"],
    "stype_in": "raw_symbol",
    "start": "2026-08-01",
    "end": "2026-09-01",
}


class FakeMetadata:
    def __init__(self, cost: float = 1.25):
        self.cost = cost
        self.calls: list[str] = []

    def get_dataset_range(self, dataset):
        self.calls.append("get_dataset_range")
        return {
            "start": "2023-03-28T00:00:00.000000000Z",
            "end": "2026-09-17T00:00:00.000000000Z",
            "schema": {
                "ohlcv-1m": {
                    "start": "2023-03-28T00:00:00.000000000Z",
                    "end": "2026-09-17T00:00:00.000000000Z",
                }
            },
        }

    def list_schemas(self, dataset):
        self.calls.append("list_schemas")
        return ["ohlcv-1m", "trades", "mbp-1"]

    def get_dataset_condition(self, dataset, start_date=None, end_date=None):
        self.calls.append("get_dataset_condition")
        return [{"date": "2026-08-01", "condition": "available"}]

    def list_unit_prices(self, dataset):
        self.calls.append("list_unit_prices")
        return [{"mode": "historical-streaming", "schema": "ohlcv-1m", "unit_price": 0.4}]

    def get_record_count(self, **kwargs):
        self.calls.append("get_record_count")
        return 18000

    def get_billable_size(self, **kwargs):
        self.calls.append("get_billable_size")
        return 4096

    def get_cost(self, **kwargs):
        self.calls.append("get_cost")
        return self.cost


class FakeTimeseries:
    def __init__(self):
        self.calls: list[dict] = []

    def get_range(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(kind="FakeDBNStore")


class FakeHistorical:
    def __init__(self, cost: float = 1.25):
        self.metadata = FakeMetadata(cost)
        self.timeseries = FakeTimeseries()


def _adapter(tmp_path, fake: FakeHistorical, monkeypatch) -> DatabentoAdapter:
    monkeypatch.setenv("DATABENTO_API_KEY", "db-test-offline-mock")
    monkeypatch.setattr(
        "level_probability_lab.providers.databento_adapter.load_dotenv",
        lambda *a, **k: None,
    )
    return DatabentoAdapter(
        root=tmp_path,
        client_factory=lambda key: fake,
        manifests_dir=tmp_path / "manifests",
    )


def test_fingerprint_changes_when_request_changes():
    a = request_fingerprint(REQUEST)
    b = request_fingerprint({**REQUEST, "end": "2026-08-15"})
    assert a != b
    assert canonical_request({**REQUEST, "symbols": ["SPY", "QQQ"]})["symbols"] == ["QQQ", "SPY"]


def test_quote_uses_metadata_only(tmp_path, monkeypatch):
    fake = FakeHistorical()
    adapter = _adapter(tmp_path, fake, monkeypatch)
    payload = adapter.quote(REQUEST)
    assert payload["timeseries_get_range_called"] is False
    assert fake.timeseries.calls == []
    assert "get_cost" in fake.metadata.calls
    assert payload["estimated_cost_usd"] == 1.25
    assert payload["request"]["dataset"] == "EQUS.MINI"


def test_unauthorized_download_is_blocked(tmp_path, monkeypatch):
    fake = FakeHistorical()
    adapter = _adapter(tmp_path, fake, monkeypatch)
    with pytest.raises(DownloadBlocked):
        adapter.download(
            REQUEST,
            download_enabled=False,
            approved=True,
            spending_cap_usd=5.0,
        )
    with pytest.raises(DownloadBlocked, match="approve"):
        adapter.download(
            REQUEST,
            download_enabled=True,
            approved=False,
            spending_cap_usd=5.0,
        )
    with pytest.raises(DownloadBlocked, match="cap"):
        adapter.download(
            REQUEST,
            download_enabled=True,
            approved=True,
            spending_cap_usd=0.0,
        )
    assert fake.timeseries.calls == []


def test_cost_cap_blocks_before_get_range(tmp_path, monkeypatch):
    fake = FakeHistorical(cost=9.99)
    adapter = _adapter(tmp_path, fake, monkeypatch)
    with pytest.raises(CostCapExceeded):
        adapter.download(
            REQUEST,
            download_enabled=True,
            approved=True,
            spending_cap_usd=5.0,
        )
    assert fake.timeseries.calls == []


def test_fingerprint_mismatch_blocks(tmp_path, monkeypatch):
    fake = FakeHistorical()
    adapter = _adapter(tmp_path, fake, monkeypatch)
    with pytest.raises(DownloadBlocked, match="fingerprint"):
        adapter.download(
            REQUEST,
            download_enabled=True,
            approved=True,
            spending_cap_usd=5.0,
            expected_fingerprint="deadbeef",
        )
    assert fake.timeseries.calls == []


def test_uncertain_failure_requires_review(tmp_path, monkeypatch):
    class BoomTimeseries(FakeTimeseries):
        def get_range(self, **kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("network dropped")

    fake = FakeHistorical(cost=1.0)
    fake.timeseries = BoomTimeseries()
    adapter = _adapter(tmp_path, fake, monkeypatch)
    with pytest.raises(UncertainChargeError):
        adapter.download(
            REQUEST,
            download_enabled=True,
            approved=True,
            spending_cap_usd=5.0,
            raw_dir=tmp_path / "raw",
        )
    assert len(fake.timeseries.calls) == 1
    with pytest.raises(UncertainChargeError, match="uncertain"):
        adapter.download(
            REQUEST,
            download_enabled=True,
            approved=True,
            spending_cap_usd=5.0,
            raw_dir=tmp_path / "raw",
        )


def test_missing_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.setattr(
        "level_probability_lab.providers.databento_adapter.load_dotenv",
        lambda *a, **k: None,
    )
    adapter = DatabentoAdapter(root=tmp_path, manifests_dir=tmp_path / "manifests")
    with pytest.raises(MissingCredentialsError):
        adapter.quote(REQUEST)


def test_approved_download_under_cap_calls_get_range(tmp_path, monkeypatch):
    fake = FakeHistorical(cost=1.0)
    adapter = _adapter(tmp_path, fake, monkeypatch)
    result = adapter.download(
        REQUEST,
        download_enabled=True,
        approved=True,
        spending_cap_usd=5.0,
        raw_dir=tmp_path / "raw",
    )
    assert result["state"] == "completed"
    assert len(fake.timeseries.calls) == 1
    reused = adapter.download(
        REQUEST,
        download_enabled=True,
        approved=True,
        spending_cap_usd=5.0,
        raw_dir=tmp_path / "raw",
    )
    assert reused.get("skipped") is True
    assert len(fake.timeseries.calls) == 1


def test_cli_download_without_approval_exits_nonzero():
    from level_probability_lab.cli import main
    from tests.conftest import ROOT

    rc = main(["--project-root", str(ROOT), "download"])
    assert rc == 2
