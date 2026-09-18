"""Direction metrics for ghost-candle forecasts.

Exact definitions
-----------------
origin_close
    Close of the last completed input bar. All moves are vs this price.

move_sign(value, origin, deadzone=0)
    +1 if value > origin + deadzone
    -1 if value < origin - deadzone
    0  otherwise (neutral / zero-change)

Forecast stance
    move_sign(point_close, origin_close).
    Persistence / zero-change forecasts have stance 0 by construction.

directional_hit
    None when stance == 0. Persistence is therefore excluded from
    directional accuracy; it is not scored as a failed direction call.
    When stance != 0: 1 if stance equals move_sign(actual_close, origin),
    else 0. An actual zero move is a miss for a non-neutral stance.

directional_accuracy
    Mean of directional_hit over the non-neutral subset only.
    Neutral rate is reported separately. We do **not** report a
    directional accuracy that treats persistence misses as 0/1 errors.

This exists because the first replay compared Kronos ~50% hit rate to a
persistence ~3% hit rate. That 3% was almost entirely actual zero-change
minutes. Persistence never took a directional stance.
"""

from __future__ import annotations


def move_sign(value: float, origin: float, deadzone: float = 0.0) -> int:
    delta = float(value) - float(origin)
    if abs(delta) <= float(deadzone):
        return 0
    return 1 if delta > 0 else -1


def directional_hit(
    forecast_close: float,
    actual_close: float,
    origin_close: float,
    deadzone: float = 0.0,
) -> float | None:
    stance = move_sign(forecast_close, origin_close, deadzone)
    if stance == 0:
        return None
    actual = move_sign(actual_close, origin_close, deadzone)
    return 1.0 if stance == actual else 0.0


def summarize_direction(hits: list[float | None]) -> dict:
    directional = [float(h) for h in hits if h is not None]
    n_dir = len(directional)
    n_neu = len(hits) - n_dir
    n = len(hits)
    return {
        "n": n,
        "n_directional": n_dir,
        "n_neutral": n_neu,
        "neutral_rate": (n_neu / n) if n else None,
        "directional_accuracy": (sum(directional) / n_dir) if n_dir else None,
        "scored_as_directional_model": n_dir > 0,
        # Explicitly refused: counting neutrals as incorrect direction calls.
        "directional_accuracy_including_neutral_as_miss": None,
    }
