import numpy as np
from level_probability_lab.bull_bear_probability import path_distribution, multiclass_scores

def test_distribution_and_scores():
    paths=np.array([[[100,101,99,100.2]]*5,[[100,101,99,99.8]]*5,[[100,101,99,100.0]]*5])
    assert np.allclose(path_distribution(paths,100),[1/3,1/3,1/3])
    b,l=multiclass_scores(np.array([0,1,2]),np.full((3,3),1/3));assert b>0 and l>0

def test_bootstrap_keeps_sessions_and_weights_by_origins():
    from level_probability_lab.bull_bear_probability import paired_session_bootstrap
    # Unequal session sizes distinguish session resampling from row resampling.
    r = paired_session_bootstrap(['a', 'a', 'a', 'b'], [[1,2]]*3 + [[-1,-2]])
    assert r['brier_delta'] == .5
    assert r['brier_delta_ci95'] == [-1, 1]
    assert r == paired_session_bootstrap(['a', 'a', 'a', 'b'], [[1,2]]*3 + [[-1,-2]])
    zero = paired_session_bootstrap(['a', 'b'], [[0,0],[0,0]])
    assert zero['brier_delta_ci95'] == [0,0]
    single = paired_session_bootstrap(['a'], [[1,1]])
    assert single['brier_delta_ci95'] == [None,None]

def test_brier_uses_unclipped_distribution():
    assert multiclass_scores([1], [[0,1,0]])[0] == 0
