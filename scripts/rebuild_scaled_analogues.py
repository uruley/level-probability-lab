"""Rebuild scaled historical-analogue forecasts and rescore. No Kronos reload."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from level_probability_lab.ghost_candles.analogues import AnalogueIndex
from level_probability_lab.ghost_candles.chart import write_replay_html
from level_probability_lab.ghost_candles.data import HISTORY_PARQUET, PILOT_PARQUET, list_complete_qqq_sessions, load_qqq_session, load_regular_qqq
from level_probability_lab.ghost_candles.env import collect_env, validate_env
from level_probability_lab.ghost_candles.evaluate import score_engine
from level_probability_lab.ghost_candles.experiment import (
    DEBUG_DAY,
    HORIZON,
    LOOKBACK,
    SAMPLE_COUNT,
    SEED,
    AnalogueForecaster,
    _breakdown,
    _leaderboard_rows,
    _reliability,
    _run_or_reuse,
)
from level_probability_lab.ghost_candles.ledger import append_ledger, write_leaderboard
from level_probability_lab.ghost_candles.storage import ForecastStore
from level_probability_lab.paths import project_root
from level_probability_lab.storage import write_json, write_parquet


def main() -> int:
    env = validate_env(collect_env())
    root = project_root()
    analogue_dir = root / "data" / "ghost_candles" / "eval" / "historical-analogue"
    if analogue_dir.exists():
        for path in analogue_dir.glob("*/forecasts.jsonl"):
            path.unlink()
            print("removed", path)

    print("fitting scaled analogue index")
    history = load_regular_qqq(HISTORY_PARQUET if HISTORY_PARQUET.exists() else PILOT_PARQUET)
    index = AnalogueIndex(lookback=LOOKBACK, horizon=HORIZON, k=SAMPLE_COUNT).fit(history)
    analogue = AnalogueForecaster(index)
    sessions = list_complete_qqq_sessions(PILOT_PARQUET)
    all_scores = []
    debug_engines = {}
    debug_bars = None
    for session in sessions:
        print("analogue", session)
        bars = load_qqq_session(PILOT_PARQUET, session)
        path = root / "data" / "ghost_candles" / "eval" / "historical-analogue" / session / "forecasts.jsonl"
        rows = _run_or_reuse(bars, analogue, path, env, session, "historical-analogue")
        for row in rows:
            row["session_date"] = session
            row["engine"] = "historical-analogue"
        all_scores.append(score_engine(rows, bars, engine="historical-analogue"))
        for engine in ("persistence", "kronos-mini", "kronos-small"):
            ep = root / "data" / "ghost_candles" / "eval" / engine / session / "forecasts.jsonl"
            erows = ForecastStore(ep).all()
            for row in erows:
                row["session_date"] = session
                row["engine"] = engine
            all_scores.append(score_engine(erows, bars, engine=engine))
        if session == DEBUG_DAY:
            debug_bars = bars
            debug_engines = {
                "kronos-small": ForecastStore(root / "data" / "ghost_candles" / "eval" / "kronos-small" / session / "forecasts.jsonl").all(),
                "kronos-mini": ForecastStore(root / "data" / "ghost_candles" / "eval" / "kronos-mini" / session / "forecasts.jsonl").all(),
                "historical-analogue": rows,
            }

    scores = pd.concat(all_scores, ignore_index=True)
    out_dir = root / "data" / "ghost_candles" / "experiments"
    write_parquet(scores, out_dir / "scores.parquet")
    reliability = _reliability(scores)
    write_parquet(reliability, out_dir / "reliability.parquet")
    pooled = _leaderboard_rows(scores, "all_complete_pilot_sessions")
    debug = _leaderboard_rows(scores.loc[scores["session_date"] == DEBUG_DAY], "debug_2026-08-14")
    other = _leaderboard_rows(scores.loc[scores["session_date"] != DEBUG_DAY], "pilot_excluding_debug_day")
    write_leaderboard(out_dir / "leaderboard.json", pooled + other + debug)
    write_json({"vol_median": float(scores["lookback_vol"].median()), "rows": _breakdown(scores)}, out_dir / "breakdown.json")
    record = {
        "experiment_id": "ghost-eval-v1b-scaled-analogues",
        "config": {
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "sample_count": SAMPLE_COUNT,
            "seed": SEED,
            "engines": ["persistence", "historical-analogue", "kronos-mini", "kronos-small"],
            "debug_day": DEBUG_DAY,
            "eval_sessions": sessions,
            "analogue_note": "subsequent analogue OHLC scaled by query_origin/analogue_origin",
            "analogue_windows": int(len(index.features) if index.features is not None else 0),
        },
        "environment": env,
        "n_score_rows": int(len(scores)),
        "leaderboard_pooled": pooled,
    }
    append_ledger(out_dir / "ledger.jsonl", record)
    write_json(record, out_dir / "latest.json")
    if debug_bars is not None:
        write_replay_html(
            root / "data" / "ghost_candles" / DEBUG_DAY / "replay.html",
            bars=debug_bars,
            session_date=DEBUG_DAY,
            symbol="QQQ",
            engines=debug_engines,
            meta={"lookback": LOOKBACK, "horizon": HORIZON, "sample_count": SAMPLE_COUNT, "seed": SEED, **env},
        )
    print("done", len(scores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
