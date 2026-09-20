"""Small deterministic ridge logistic regression for the frozen companion study."""
import numpy as np


def sigmoid(z):
    return np.exp(-np.logaddexp(0, -np.asarray(z)))


def fit(x, y, penalty=.1):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or set(np.unique(y))!={0.,1.}:
        raise ValueError('Finite inputs and both binary classes required')
    mean=x.mean(axis=0);std=x.std(axis=0);keep=std>1e-12
    a=np.column_stack([np.ones(len(x)),(x[:,keep]-mean[keep])/std[keep]])
    beta=np.zeros(a.shape[1]);beta[0]=np.log(y.mean()/(1-y.mean()))
    ridge=np.full(len(beta),penalty);ridge[0]=0
    def objective(b):
        z=a@b
        return np.mean(np.logaddexp(0,z)-y*z)+.5*np.sum(ridge*b*b)
    for iteration in range(100):
        p=sigmoid(a@beta)
        gradient=a.T@(p-y)/len(y)+ridge*beta
        if np.max(np.abs(gradient))<1e-8:break
        hessian=(a.T*(p*(1-p)))@a/len(y)+np.diag(ridge)
        direction=np.linalg.solve(hessian,gradient)
        step=1.
        while objective(beta-step*direction)>objective(beta)-1e-4*step*(gradient@direction):
            step*=.5
            if step<1e-12:raise ValueError('Line search failed')
        beta-=step*direction
    else:raise ValueError('Fit did not converge')
    return dict(mean=mean.tolist(),std=std.tolist(),keep=keep.tolist(),beta=beta.tolist(),
                penalty=penalty,iterations=iteration,gradient_max=float(np.max(np.abs(gradient))))


def predict(model,x):
    x=np.asarray(x,float);keep=np.asarray(model['keep'],bool)
    return sigmoid(np.column_stack([np.ones(len(x)),(x[:,keep]-np.array(model['mean'])[keep])/np.array(model['std'])[keep]])@np.array(model['beta']))
