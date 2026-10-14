"""Shared analysis primitives for the child-vs-adult segregation claim.

Used by the batch generator (to compute ground truth and run the gates) and vendored
into each task's solution/ so the oracle runs the exact same code.

Data layout expected in a data directory (pool or task variant):
    participants.tsv           subject, age, group  (group in {"child", "adult"})
    timeseries/<subject>.npy   (timepoints, ROIs) float32, no denoising applied
    confounds/<subject>.tsv    fMRIPrep-style confound columns
    roi_coords.csv             x, y, z for each ROI column, in order
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist

TR = 2.0
MOTION6 = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]
NUISANCE_EXTRA = ["csf", "white_matter"]


# --------------------------------------------------------------------------- motion
def framewise_displacement(conf: pd.DataFrame, head_radius_mm: float = 50.0) -> np.ndarray:
    """Power et al. (2012) FD. Uses fMRIPrep's column if present, else computes it."""
    if "framewise_displacement" in conf.columns:
        return np.nan_to_num(conf["framewise_displacement"].to_numpy(float), nan=0.0)
    m = conf[MOTION6].to_numpy(float)
    d = np.abs(np.diff(m, axis=0))
    d[:, 3:] *= head_radius_mm  # radians -> mm of arc on a 50 mm sphere
    return np.r_[0.0, d.sum(axis=1)]


def mean_fd(conf: pd.DataFrame) -> float:
    return float(np.mean(framewise_displacement(conf)[1:]))


# --------------------------------------------------------------------------- connectivity
def clean_timeseries(ts: np.ndarray, conf: pd.DataFrame, t_r: float = TR) -> np.ndarray:
    """'Common practice' denoising: 6 motion params + WM + CSF, detrend, band-pass."""
    import warnings

    from nilearn import signal

    cols = [c for c in MOTION6 + NUISANCE_EXTRA if c in conf.columns]
    X = np.nan_to_num(conf[cols].to_numpy(float)) if cols else None
    with warnings.catch_warnings():  # nilearn 0.12 warns about its internal confound z-scoring
        warnings.simplefilter("ignore", DeprecationWarning)
        return signal.clean(
            ts, confounds=X, detrend=True, standardize="zscore_sample",
            low_pass=0.08, high_pass=0.009, t_r=t_r,
        )


def distance_masks(coords: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks over the condensed upper triangle: bottom / top distance tertile.

    pdist's condensed order matches np.triu_indices(n, k=1), which segregation() uses.
    """
    d = pdist(coords)
    lo, hi = np.quantile(d, [1 / 3, 2 / 3])
    return d <= lo, d >= hi


def segregation(ts_clean: np.ndarray, short_mask: np.ndarray, long_mask: np.ndarray):
    r = np.corrcoef(ts_clean.T)
    iu = np.triu_indices_from(r, k=1)
    z = np.arctanh(np.clip(r[iu], -0.999999, 0.999999))
    s = float(np.nanmean(z[short_mask]))
    l = float(np.nanmean(z[long_mask]))
    return s, l, s - l


def subject_table(data_dir: str | Path) -> pd.DataFrame:
    """One row per subject: group, age, mean_fd, short_range, long_range, segregation."""
    data_dir = Path(data_dir)
    parts = pd.read_csv(data_dir / "participants.tsv", sep="\t")
    coords = pd.read_csv(data_dir / "roi_coords.csv")[["x", "y", "z"]].to_numpy(float)
    short_mask, long_mask = distance_masks(coords)
    rows = []
    for _, p in parts.iterrows():
        ts = np.load(data_dir / "timeseries" / f"{p.subject}.npy")
        conf = pd.read_csv(data_dir / "confounds" / f"{p.subject}.tsv", sep="\t")
        s, l, g = segregation(clean_timeseries(ts, conf), short_mask, long_mask)
        rows.append(dict(subject=p.subject, group=p.group, age=float(p.age),
                         mean_fd=mean_fd(conf), short_range=s, long_range=l, segregation=g))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- the claim
def group_effect(df: pd.DataFrame, col: str = "segregation", alpha: float = 0.05) -> dict:
    """Claim: children show higher segregation than adults (Welch t-test)."""
    c = df.loc[df.group == "child", col].to_numpy(float)
    a = df.loc[df.group == "adult", col].to_numpy(float)
    if len(c) < 3 or len(a) < 3:
        return dict(effect=float("nan"), se=float("nan"), p=float("nan"),
                    supported=False, n_child=len(c), n_adult=len(a))
    t, p = stats.ttest_ind(c, a, equal_var=False)
    se = float(np.sqrt(c.var(ddof=1) / len(c) + a.var(ddof=1) / len(a)))
    effect = float(c.mean() - a.mean())
    return dict(effect=effect, se=se, p=float(p),
                supported=bool(effect > 0 and p < alpha), n_child=len(c), n_adult=len(a))
