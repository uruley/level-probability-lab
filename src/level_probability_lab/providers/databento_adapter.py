from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from level_probability_lab.exceptions import (
    CostCapExceeded,
    DownloadBlocked,
    MissingCredentialsError,
    UncertainChargeError,
)
from level_probability_lab.paths import ensure_dir, project_root
from level_probability_lab.storage import read_json, write_json

# Documentation-backed dataset notes. Not used to invent coverage or prices.
DATASET_NOTES = {
    "EQUS.MINI": {
        "feed_type": "derived_multi_venue_aggregate",
        "volume": (
            "OHLCV prices and volume are aggregated across EQUS.MINI component "
            "venues (ATS + selected Reg NMS). This is not full SIP/NMS consolidated volume."
        ),
        "history_start_documented": "2023-03-28",
        "history_note": (
            "Documented historical start is 2023-03-28. This dataset alone cannot "
            "satisfy an ~8-year history goal."
        ),
        "suitability": (
            "Chosen for the Phase 1 pilot because it covers QQQ and SPY with "
            "1-minute OHLCV and multi-venue aggregated volume. Not chosen because it is cheapest."
        ),
        "docs": [
            "https://databento.com/docs/venues-and-datasets/equs-mini",
            "https://databento.com/blog/databento-us-equities-mini-now-available",
        ],
    },
    "XNAS.ITCH": {
        "feed_type": "venue_specific",
        "volume": (
            "Nasdaq prints only. QQQ, NVDA, and TSLA are Nasdaq-listed, so this is the "
            "primary-listing venue, not full US consolidated volume."
        ),
        "history_start_documented": "2018-05-01",
        "suitability": (
            "Longer history than EQUS.MINI, but venue-specific volume makes it a poor "
            "pilot for QQQ+SPY together."
        ),
        "docs": ["https://databento.com/datasets/XNAS.ITCH"],
    },
    "EQUS.SUMMARY": {
        "feed_type": "consolidated_daily_summary",
        "volume": "Consolidated volume, but only daily/statistics schemas — not 1-minute OHLCV.",
        "suitability": "Rejected for Phase 1 1-minute labels.",
        "docs": ["https://databento.com/docs/venues-and-datasets/equs-summary"],
    },
}

QUOTE_METADATA_METHODS = (
    "get_dataset_range",
    "list_schemas",
    "get_dataset_condition",
    "list_unit_prices",
    "get_record_count",
    "get_billable_size",
    "get_cost",
)

GET_COST_CAVEAT = (
    "Databento documents that metadata.get_cost and get_record_count may over-report "
    "for time ranges that are not discrete multiples of 10 minutes."
)

STREAMING_BILLING_CAVEAT = (
    "Historical market data is billed per uncompressed binary byte sent. If a streaming "
    "request disconnects, remaining unsent data is not charged, but this tool cannot see "
    "the invoice. After any failure that occurs once get_range has started, the chunk is "
    "marked uncertain_charge and will not be retried without --acknowledge-prior-failure."
)

METADATA_BILLING_CAVEAT = (
    "Quote uses only Historical.metadata methods. Databento meters historical data as "
    "binary market-data bytes from timeseries/batch requests. There is no single FAQ "
    "sentence that metadata HTTP calls are never billed; residual uncertainty is recorded "
    "on every quote."
)


def canonical_request(request: dict[str, Any]) -> dict[str, Any]:
    symbols = request["symbols"]
    if isinstance(symbols, str):
        symbol_list = [symbols]
    else:
        symbol_list = [str(s) for s in symbols]
    return {
        "dataset": str(request["dataset"]),
        "schema": str(request["schema"]),
        "symbols": sorted(symbol_list),
        "stype_in": str(request.get("stype_in") or "raw_symbol"),
        "start": str(request["start"]),
        "end": str(request["end"]),
    }


def request_fingerprint(request: dict[str, Any]) -> str:
    payload = json.dumps(canonical_request(request), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_api_key(root: Path | None = None) -> str:
    root = root or project_root()
    load_dotenv(root / ".env", override=False)
    return os.environ.get("DATABENTO_API_KEY", "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_factory_default(key: str):
    try:
        import databento as db
    except ImportError as exc:
        raise DownloadBlocked(
            'The databento package is not installed. Run: pip install -e ".[databento]"'
        ) from exc
    return db.Historical(key)


class DatabentoAdapter:
    """Offline-safe adapter. Quote uses metadata only. Download is guarded."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        client_factory: Callable[[str], Any] | None = None,
        manifests_dir: Path | None = None,
    ) -> None:
        self.root = root or project_root()
        self.client_factory = client_factory or _client_factory_default
        self.manifests_dir = manifests_dir or (self.root / "data" / "manifests")

    def _require_key(self) -> str:
        key = load_api_key(self.root)
        if not key:
            raise MissingCredentialsError(
                "DATABENTO_API_KEY is not set. Put it in a local .env (see .env.example) "
                "or a user environment variable. Do not paste the key into chat."
            )
        return key

    def _client(self):
        return self.client_factory(self._require_key())

    def quote(self, request: dict[str, Any]) -> dict[str, Any]:
        canon = canonical_request(request)
        fingerprint = request_fingerprint(canon)
        client = self._client()
        metadata = client.metadata
        calls: list[str] = []

        def _call(name: str, fn, **kwargs):
            calls.append(name)
            return fn(**kwargs)

        dataset = canon["dataset"]
        start = canon["start"]
        end = canon["end"]
        dataset_range = _call("get_dataset_range", metadata.get_dataset_range, dataset=dataset)
        schemas = _call("list_schemas", metadata.list_schemas, dataset=dataset)
        condition = _call(
            "get_dataset_condition",
            metadata.get_dataset_condition,
            dataset=dataset,
            start_date=start,
            end_date=end,
        )
        unit_prices = _call("list_unit_prices", metadata.list_unit_prices, dataset=dataset)
        common = dict(
            dataset=dataset,
            start=start,
            end=end,
            symbols=canon["symbols"],
            schema=canon["schema"],
            stype_in=canon["stype_in"],
        )
        record_count = _call("get_record_count", metadata.get_record_count, **common)
        billable_size = _call("get_billable_size", metadata.get_billable_size, **common)
        cost = _call("get_cost", metadata.get_cost, **common)

        schema_range = None
        if isinstance(dataset_range, dict):
            schema_map = dataset_range.get("schema") or dataset_range.get("range_by_schema")
            if isinstance(schema_map, dict):
                schema_range = schema_map.get(canon["schema"])

        payload = {
            "kind": "quote_only",
            "created_at": _now_iso(),
            "fingerprint": fingerprint,
            "request": canon,
            "estimated_cost_usd": float(cost) if cost is not None else None,
            "record_count": record_count,
            "billable_size_bytes": billable_size,
            "dataset_range": dataset_range,
            "schema_range": schema_range,
            "schemas": schemas,
            "dataset_condition": condition,
            "unit_prices": unit_prices,
            "dataset_notes": DATASET_NOTES.get(dataset, {"feed_type": "see official docs"}),
            "metadata_methods_called": calls,
            "timeseries_get_range_called": False,
            "caveats": [
                GET_COST_CAVEAT,
                METADATA_BILLING_CAVEAT,
                STREAMING_BILLING_CAVEAT,
            ],
            "live_data": False,
            "subscription_activated": False,
        }
        quote_path = ensure_dir(self.manifests_dir / "quotes") / f"{fingerprint}.json"
        write_json(payload, quote_path)
        payload["quote_path"] = str(quote_path)
        return payload

    def _download_manifest_path(self, fingerprint: str) -> Path:
        return ensure_dir(self.manifests_dir / "downloads") / f"{fingerprint}.json"

    def _prior_state(self, fingerprint: str) -> dict[str, Any] | None:
        path = self._download_manifest_path(fingerprint)
        if path.exists():
            return read_json(path)
        return None

    def download(
        self,
        request: dict[str, Any],
        *,
        download_enabled: bool,
        approved: bool,
        spending_cap_usd: float,
        acknowledge_prior_failure: bool = False,
        expected_fingerprint: str | None = None,
        raw_dir: Path | None = None,
    ) -> dict[str, Any]:
        canon = canonical_request(request)
        fingerprint = request_fingerprint(canon)
        if expected_fingerprint and expected_fingerprint != fingerprint:
            raise DownloadBlocked(
                "Request fingerprint does not match --expected-fingerprint. "
                "A changed request requires a new quote and a new approval."
            )
        if not download_enabled:
            raise DownloadBlocked("Download is disabled (download_enabled is false / missing --enable-download).")
        if not approved:
            raise DownloadBlocked("Missing --i-approve-this-exact-request.")
        if spending_cap_usd is None or float(spending_cap_usd) <= 0:
            raise DownloadBlocked("Spending cap is $0. Pass --spending-cap with a positive USD amount.")

        prior = self._prior_state(fingerprint)
        if prior and prior.get("state") == "completed":
            return {**prior, "skipped": True, "reason": "already_completed_local_reuse"}
        if prior and prior.get("state") in {"uncertain_charge", "failed_after_request_started"}:
            if not acknowledge_prior_failure:
                raise UncertainChargeError(
                    "A previous download for this exact request ended in an uncertain charge state. "
                    "Review data/manifests/downloads and the Databento portal before retrying. "
                    "Re-run with --acknowledge-prior-failure only after that review."
                )

        client = self._client()
        cost = float(
            client.metadata.get_cost(
                dataset=canon["dataset"],
                start=canon["start"],
                end=canon["end"],
                symbols=canon["symbols"],
                schema=canon["schema"],
                stype_in=canon["stype_in"],
            )
        )
        if cost > float(spending_cap_usd):
            raise CostCapExceeded(
                f"Fresh get_cost estimate ${cost:.4f} exceeds spending cap ${float(spending_cap_usd):.4f}."
            )

        raw_dir = Path(raw_dir) if raw_dir is not None else self.root / "data" / "raw"
        ensure_dir(raw_dir)
        raw_path = raw_dir / f"{canon['dataset'].replace('.', '_')}_{fingerprint[:12]}.ohlcv-1m.dbn.zst"
        manifest = {
            "kind": "download",
            "created_at": _now_iso(),
            "fingerprint": fingerprint,
            "request": canon,
            "state": "requested",
            "quoted_cost_usd": cost,
            "spending_cap_usd": float(spending_cap_usd),
            "raw_path": str(raw_path),
            "timeseries_get_range_called": False,
            "caveats": [GET_COST_CAVEAT, STREAMING_BILLING_CAVEAT],
        }
        write_json(manifest, self._download_manifest_path(fingerprint))

        try:
            manifest["timeseries_get_range_called"] = True
            write_json(manifest, self._download_manifest_path(fingerprint))
            store = client.timeseries.get_range(
                dataset=canon["dataset"],
                start=canon["start"],
                end=canon["end"],
                symbols=canon["symbols"],
                schema=canon["schema"],
                stype_in=canon["stype_in"],
                path=str(raw_path),
            )
        except Exception as exc:
            manifest["state"] = "uncertain_charge"
            manifest["error"] = repr(exc)
            manifest["finished_at"] = _now_iso()
            write_json(manifest, self._download_manifest_path(fingerprint))
            raise UncertainChargeError(
                "Download failed after timeseries.get_range was invoked. Not retrying. "
                "Inspect the Databento portal for any charge, then review the manifest."
            ) from exc

        manifest["state"] = "completed"
        manifest["finished_at"] = _now_iso()
        manifest["store_type"] = type(store).__name__
        write_json(manifest, self._download_manifest_path(fingerprint))
        return manifest
