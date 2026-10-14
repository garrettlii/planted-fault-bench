"""SYNTHETIC pool for offline smoke tests ONLY. Never use it to evaluate a model.

Mimics the structure of the real pool so the whole pipeline (gates, materialization,
oracle, verifier, aggregation) can be exercised without downloading ds000228:
  * 122 children + 33 adults, 168 volumes, TR 2 s, real Power-264 coordinates
  * no true developmental effect
  * children move more; motion adds a spatially smooth artifact whose strength scales
    with the subject's motion, which inflates short-range relative to long-range
    connectivity (the Power et al. 2012 signature)

    python -m pfbench.mock_pool --out /tmp/mock_pool
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

from .analysis import MOTION6, framewise_displacement


def make(out: Path, seed: int = 0, n_child: int = 122, n_adult: int = 33, T: int = 168,
         artifact_gain: float = 2.5):
    from nilearn import datasets

    rng = np.random.default_rng(seed)
    coords = pd.DataFrame(datasets.fetch_coords_power_2011().rois)[["x", "y", "z"]].to_numpy(float)
    R = len(coords)
    net = rng.integers(0, 10, R)  # latent "network" membership
    (out / "timeseries").mkdir(parents=True, exist_ok=True)
    (out / "confounds").mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(n_child + n_adult):
        child = i < n_child
        sid = f"sub-mock{i:03d}"
        age = rng.uniform(3.5, 12) if child else rng.uniform(18, 39)
        target_fd = float(np.exp(rng.normal(np.log(0.30 if child else 0.14), 0.55 if child else 0.30)))
        # motion parameters whose Power FD averages ~target_fd
        steps = rng.standard_normal((T - 1, 6)) * np.r_[[1.0] * 3, [1 / 50] * 3]
        steps *= target_fd / np.mean(np.abs(steps[:, :3]).sum(1) + 50 * np.abs(steps[:, 3:]).sum(1))
        motion = np.vstack([np.zeros(6), np.cumsum(steps, axis=0)])
        conf = pd.DataFrame(motion, columns=MOTION6)
        conf["framewise_displacement"] = framewise_displacement(conf)
        conf["csf"] = rng.standard_normal(T)
        conf["white_matter"] = rng.standard_normal(T)
        # neural signal: 10 latent networks, identical statistics for both groups
        sources = rng.standard_normal((T, 10))
        ts = sources[:, net] * 0.8 + rng.standard_normal((T, R))
        # motion artifact: FD-driven time courses, spatially smooth around 4 random centers
        fd = conf["framewise_displacement"].to_numpy()
        centers = coords[rng.choice(R, 4, replace=False)]
        w = np.exp(-cdist(coords, centers) / 25.0)  # (R, 4)
        drive = (fd[:, None] - fd.mean()) * rng.uniform(0.5, 1.5, 4) + 0.3 * target_fd * rng.standard_normal((T, 4))
        ts += artifact_gain * drive @ w.T
        np.save(out / "timeseries" / f"{sid}.npy", ts.astype(np.float32))
        conf.to_csv(out / "confounds" / f"{sid}.tsv", sep="\t", index=False)
        rows.append({"subject": sid, "age": round(age, 2), "group": "child" if child else "adult"})
    pd.DataFrame(rows).to_csv(out / "participants.tsv", sep="\t", index=False)
    pd.DataFrame(coords, columns=["x", "y", "z"]).to_csv(out / "roi_coords.csv", index=False)
    (out / "SYNTHETIC_DO_NOT_EVALUATE").write_text("mock pool for smoke tests\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--artifact-gain", type=float, default=2.5)
    a = ap.parse_args()
    make(Path(a.out), a.seed, artifact_gain=a.artifact_gain)


if __name__ == "__main__":
    main()
