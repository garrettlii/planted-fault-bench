"""Signal detection theory and psychometric fitting for detection responses.

Response = "agent reported a concern naming the fault, marked as affecting its
conclusion". Signal = variant is faulty.

    d'  = z(H) - z(FA)           sensitivity: separates faulty from clean
    c   = -(z(H) + z(FA)) / 2    bias: c < 0 flags too readily, c > 0 trusts too readily

Rates use the log-linear correction (Hautus 1995): (count + 0.5) / (n + 1), so perfect
or zero rates give finite z and small samples are shrunk toward 0.5.
"""
from __future__ import annotations

from statistics import NormalDist

import numpy as np

_z = NormalDist().inv_cdf


def rates(hits: int, n_signal: int, fas: int, n_noise: int) -> tuple[float, float]:
    return (hits + 0.5) / (n_signal + 1), (fas + 0.5) / (n_noise + 1)


def dprime_c(hits: int, n_signal: int, fas: int, n_noise: int) -> dict:
    H, FA = rates(hits, n_signal, fas, n_noise)
    return {"H": H, "FA": FA, "dprime": _z(H) - _z(FA), "c": -(_z(H) + _z(FA)) / 2}


def logistic_fit(x: np.ndarray, y: np.ndarray, ridge: float = 1e-3, iters: int = 100):
    """P(detect) = sigmoid(b0 + b1 x), Newton-Raphson with a small ridge (handles separation)."""
    X = np.c_[np.ones_like(x), x]
    b = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ b)))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(2)
        step = np.linalg.solve(H, X.T @ (y - p) - ridge * b)
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return b


def threshold(x, y) -> float | None:
    """Fault strength (x units) at which detection probability is 0.5, if it is in range."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(np.unique(y)) < 2 or len(x) < 4:
        return None
    b0, b1 = logistic_fit(x, y)
    if b1 <= 0:
        return None
    t = -b0 / b1
    return float(t) if x.min() <= t <= x.max() * 1.5 else None
