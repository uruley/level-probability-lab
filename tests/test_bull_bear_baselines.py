import pandas as pd
from level_probability_lab.bull_bear_baselines import label_return, summarize


def test_boundaries_and_summary_are_explicit():
    assert label_return(100, 100.1) == "neutral"
    assert label_return(100, 100.10001) == "bull"
    assert label_return(100, 99.9) == "neutral"
    assert label_return(100, 99.89999) == "bear"
    rows = pd.DataFrame({
        "engine": ["persistence", "persistence"], "horizon_minutes": [5, 5],
        "session_date": ["2026-08-01", "2026-08-01"],
        "origin_close": [100, 100], "actual_close": [100.2, 99.8],
        "median_close": [100, 100.2], "median_close_abs_error": [.2, .4],
    })
    result = summarize(rows)
    assert result["probability_status"] == "not_available"
    assert result["rows"][0]["actual_counts"] == {"bull": 1, "neutral": 0, "bear": 1}
