"""Offline Jev companion package and response contract."""
from __future__ import annotations

import math
import json
import os
import hashlib
from pathlib import Path
import urllib.request
from typing import Any


CLASSES = ("bull", "neutral", "bear")


def build_package(*, forecast_id: str, origin: str, session: str,
                  origin_close: float, sampled_paths: Any,
                  kronos_median: Any, kronos_range: Any,
                  label_spec: str = "close_return_pm_10bp_v1",
                  location: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a point-in-time-only package; caller supplies already frozen data."""
    if not forecast_id or not origin or not session:
        raise ValueError("forecast identity and timestamps are required")
    if not math.isfinite(float(origin_close)):
        raise ValueError("origin_close must be finite")
    return {"schema_version": "jev_companion_input_v1", "forecast_id": forecast_id,
            "origin": origin, "session": session, "origin_close": float(origin_close),
            "sampled_paths": sampled_paths, "kronos_median": kronos_median,
            "kronos_range": kronos_range, "label_spec": label_spec,
            "location": location, "input_complete": True}


def parse_response(value: dict[str, Any]) -> dict[str, Any]:
    """Validate Jev's structured output without treating scores as calibrated."""
    if not isinstance(value, dict):
        raise ValueError("response must be an object")
    scores = value.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(CLASSES):
        raise ValueError("scores must contain exactly bull, neutral, bear")
    if any(type(scores[name]) not in (float, int) for name in CLASSES):
        raise ValueError("scores must be numeric")
    parsed = {name: float(scores[name]) for name in CLASSES}
    if any(not math.isfinite(v) or v < 0 or v > 1 for v in parsed.values()):
        raise ValueError("scores must be finite values in [0, 1]")
    if not math.isclose(sum(parsed.values()), 1.0, abs_tol=1e-6):
        raise ValueError("scores must sum to one")
    if type(value.get("input_complete")) is not bool:
        raise ValueError("input_complete must be boolean")
    reason = value.get("reason", "")
    if not isinstance(reason, str):
        raise ValueError("reason must be text")
    return {"scores": parsed, "reason": reason,
            "input_complete": bool(value.get("input_complete", False)),
            "probability_status": "unvalidated_model_scores"}


def mock_choice(package: dict[str, Any]) -> dict[str, Any]:
    """Deterministic fixture transport used before any real Jev access."""
    if package.get("schema_version") != "jev_companion_input_v1":
        raise ValueError("unsupported package")
    return parse_response({"scores": {"bull": .2, "neutral": .6, "bear": .2},
                           "reason": "offline fixture", "input_complete": True})


def parse_typesafe(body: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(body, dict) or not isinstance(body.get("model"), str) or not body["model"]:
        raise ValueError("missing response model version")
    choice = body.get("answers", {}).get("move_5m", {})
    if choice.get("type") != "choice" or choice.get("choice") not in CLASSES:
        raise ValueError("missing Choice answer")
    raw_scores = choice.get("probabilities")
    if not isinstance(raw_scores, dict) or set(raw_scores) != set(CLASSES):
        raise ValueError("invalid probability keys")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
           for v in raw_scores.values()):
        raise ValueError("invalid probabilities")
    total = sum(raw_scores.values())
    # Observed API output uses two decimals. Allow only the rounding envelope
    # of three rounded values; retain raw output and explicitly label rescaling.
    if abs(total - 1) > .015000001:
        raise ValueError("probability sum exceeds rounding tolerance")
    result = parse_response({"scores": {k: v / total for k, v in raw_scores.items()}, "reason": "",
                             "input_complete": True})
    confidence = choice.get("confidence")
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("invalid confidence")
    return dict(result, model=body["model"], choice=choice["choice"],
                confidence=confidence, usage=body.get("usage"), raw_scores=raw_scores,
                raw_score_sum=total, normalization="divide_by_observed_sum")


def request_real(package: dict[str, Any], *, api_key: str | None = None,
                 model: str = "jev-latest", timeout: int = 30,
                 allow_network: bool = False, cache_dir=None) -> dict[str, Any]:
    """Make one explicitly requested TypeSafe request and validate its Choice."""
    if cache_dir is None:
        raise ValueError("durable pilot cache is required")
    key = api_key or os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise ValueError("TYPESAFE_API_KEY is required")
    payload = {"model": model, "state": package,
               "questions": {"move_5m": {"type": "choice",
                 "instructions": "Classify the fixed five-minute QQQ outcome using only this state.",
                 "criteria": {"bull": "return > +10bp", "neutral": "return between -10bp and +10bp inclusive", "bear": "return < -10bp"}}}}
    encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    response_path = cache / (digest + '.response.json')
    if response_path.exists():
        result = parse_typesafe(json.loads(response_path.read_text()))
        (cache / 'result.json').write_text(json.dumps(result, indent=2))
        (cache / 'attempt.json').write_text(json.dumps(dict(request_sha256=digest,
            status='validated_from_cache', request_limit=1, cost_usd=None)))
        return result
    if not allow_network:
        raise ValueError("network disabled")
    # Exclusive reservation enforces one request across restarts/processes.
    # An uncertain request is never automatically retried.
    with (cache / 'attempt.json').open('x') as f:
        json.dump(dict(request_sha256=digest, status='uncertain_charge', request_limit=1), f)
    (cache / (digest + '.request.json')).write_bytes(encoded)
    request = urllib.request.Request("https://api.typesafe.ai/v1/systemone",
        data=encoded, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    response_path.write_bytes(raw)  # Preserve before parsing; replay costs nothing.
    result = parse_typesafe(json.loads(raw))
    (cache / 'result.json').write_text(json.dumps(result, indent=2))
    (cache / 'attempt.json').write_text(json.dumps(dict(request_sha256=digest,
        status='validated', request_limit=1, cost_usd=None)))
    return result
