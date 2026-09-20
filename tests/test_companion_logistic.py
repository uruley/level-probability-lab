import numpy as np
from level_probability_lab.companion_logistic import fit,predict


def test_constant_features_recover_class_frequency():
    x=np.ones((10,2));y=np.array([1]*3+[0]*7)
    m=fit(x,y)
    np.testing.assert_allclose(predict(m,x),.3,atol=1e-8)
    assert not any(m['keep'])


def test_signal_monotonic_and_training_scaler_frozen():
    x=np.arange(100,dtype=float).reshape(-1,1);y=(x[:,0]>=50).astype(float)
    m=fit(x,y);before=repr(m)
    p=predict(m,x)
    assert np.all(np.diff(p)>0) and p[0]<.5<p[-1]
    assert m['gradient_max']<1e-8
    predict(m,[[100000]])
    assert repr(m)==before
    np.testing.assert_allclose(predict(fit(x,y),x),p)
