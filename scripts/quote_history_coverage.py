"""Re-quote the multi-year request and record coverage. Metadata only."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from level_probability_lab.config import databento_request_from_config, load_config
from level_probability_lab.paths import ensure_data_layout, project_root
from level_probability_lab.providers.databento_adapter import (
    DatabentoAdapter,
    canonical_request,
    request_fingerprint,
)
from level_probability_lab.storage import write_json


def _client(root: Path):
    adapter = DatabentoAdapter(root=root)
    return adapter._client(), adapter


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs" / "history_xnas_ohlcv1m.yaml", root=root)
    layout = ensure_data_layout(root, "data")
    request = databento_request_from_config(cfg)
    # Canonical UTC timestamps as requested (inclusive start, exclusive end).
    request["start"] = "2018-05-01T00:00:00Z"
    request["end"] = "2026-09-01T00:00:00Z"
    request = canonical_request(request)

    adapter = DatabentoAdapter(root=root)
    combined = adapter.quote(request)
    client = adapter._client()

    per_symbol = []
    for symbol in request["symbols"]:
        part = {
            "dataset": request["dataset"],
            "schema": request["schema"],
            "symbols": [symbol],
            "stype_in": request["stype_in"],
            "start": request["start"],
            "end": request["end"],
        }
        cost = float(
            client.metadata.get_cost(
                dataset=part["dataset"],
                start=part["start"],
                end=part["end"],
                symbols=part["symbols"],
                schema=part["schema"],
                stype_in=part["stype_in"],
            )
        )
        records = client.metadata.get_record_count(
            dataset=part["dataset"],
            start=part["start"],
            end=part["end"],
            symbols=part["symbols"],
            schema=part["schema"],
            stype_in=part["stype_in"],
        )
        size = client.metadata.get_billable_size(
            dataset=part["dataset"],
            start=part["start"],
            end=part["end"],
            symbols=part["symbols"],
            schema=part["schema"],
            stype_in=part["stype_in"],
        )
        per_symbol.append(
            {
                "symbol": symbol,
                "estimated_cost_usd": cost,
                "record_count": records,
                "billable_size_bytes": size,
                "fingerprint": request_fingerprint(part),
            }
        )

    edge_windows = [
        ("dataset_open_week", "2018-05-01T00:00:00Z", "2018-05-08T00:00:00Z"),
        ("last_week_before_end", "2026-08-24T00:00:00Z", "2026-09-01T00:00:00Z"),
    ]
    edges = []
    for name, start, end in edge_windows:
        row = {"window": name, "start": start, "end": end, "symbols": {}}
        for symbol in request["symbols"]:
            row["symbols"][symbol] = {
                "record_count": client.metadata.get_record_count(
                    dataset=request["dataset"],
                    start=start,
                    end=end,
                    symbols=[symbol],
                    schema=request["schema"],
                    stype_in=request["stype_in"],
                ),
                "estimated_cost_usd": float(
                    client.metadata.get_cost(
                        dataset=request["dataset"],
                        start=start,
                        end=end,
                        symbols=[symbol],
                        schema=request["schema"],
                        stype_in=request["stype_in"],
                    )
                ),
            }
        edges.append(row)

    resolve = client.symbology.resolve(
        dataset=request["dataset"],
        symbols=request["symbols"],
        stype_in=request["stype_in"],
        stype_out="instrument_id",
        start_date="2018-05-01",
        end_date="2026-09-01",
    )

    condition = combined.get("dataset_condition") or []
    cond_counts = Counter(str(row.get("condition")) for row in condition)

    schemas = combined.get("schemas") or []
    schema_ok = request["schema"] in schemas
    schema_range = combined.get("schema_range")
    total = float(combined["estimated_cost_usd"])
    ceiling = 5.0

    payload = {
        "kind": "history_quote_with_coverage",
        "authorization": "not_granted",
        "proposed_ceiling_usd": ceiling,
        "ceiling_is_authorization": False,
        "download_enabled": False,
        "within_proposed_ceiling": total <= ceiling,
        "request": request,
        "request_start_utc_inclusive": request["start"],
        "request_end_utc_exclusive": request["end"],
        "fingerprint": combined["fingerprint"],
        "combined_quote": {
            "estimated_cost_usd": combined["estimated_cost_usd"],
            "record_count": combined["record_count"],
            "billable_size_bytes": combined["billable_size_bytes"],
            "quote_path": combined.get("quote_path"),
        },
        "schema_listed_for_dataset": schema_ok,
        "available_schemas": schemas,
        "dataset_range": combined.get("dataset_range"),
        "schema_range_ohlcv_1m": schema_range,
        "per_symbol": per_symbol,
        "edge_windows": edges,
        "symbology_resolve": resolve if isinstance(resolve, dict) else str(type(resolve)),
        "dataset_condition_counts": dict(cond_counts),
        "dataset_condition_n_days": len(condition),
        "feed_notes": combined.get("dataset_notes"),
        "timeseries_get_range_called": False,
        "caveats": combined.get("caveats"),
    }
    out = layout["quotes"] / f"history_coverage_{combined['fingerprint']}.json"
    write_json(payload, out)
    print(json.dumps({k: payload[k] for k in (
        "request",
        "fingerprint",
        "combined_quote",
        "schema_listed_for_dataset",
        "schema_range_ohlcv_1m",
        "per_symbol",
        "edge_windows",
        "dataset_condition_counts",
        "within_proposed_ceiling",
        "authorization",
        "proposed_ceiling_usd",
    )}, indent=2, default=str))
    print("saved", out)


if __name__ == "__main__":
    main()
