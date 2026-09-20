"""Quote two fixed QQQ trades requests using metadata only; never download."""
from __future__ import annotations

import json
import yaml

from level_probability_lab.paths import project_root
from level_probability_lab.providers.databento_adapter import DatabentoAdapter, canonical_request
from level_probability_lab.storage import write_json


def main() -> None:
    root = project_root()
    cfg = yaml.safe_load((root / "configs/databento_trades_study.yaml").read_text())
    assert cfg["databento"]["download_enabled"] is False
    assert cfg["databento"]["spending_cap_usd"] == 0
    full = canonical_request(cfg["databento"])
    sample = {**full, **cfg["study"]["setup_sample"]}
    adapter = DatabentoAdapter(root=root)
    rows = []
    for name, request in [("three_month_full_day", full), ("one_session_setup", sample)]:
        quote = adapter.quote(request)
        row = {"name": name, **{key: quote[key] for key in (
            "request", "fingerprint", "estimated_cost_usd", "record_count",
            "billable_size_bytes", "quote_path", "created_at")}}
        rows.append(row)
        print(json.dumps(row, indent=2))
    payload = {"kind": "trades_study_quote_only", "authorization": "not_granted",
               "download_enabled": False, "spending_cap_usd": 0,
               "timeseries_get_range_called": False, "quotes": rows,
               "study": cfg["study"]}
    write_json(payload, root / "data/manifests/quotes/trades_study.json")


if __name__ == "__main__":
    main()
