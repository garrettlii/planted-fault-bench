"""Drop ROI columns that are constant or nearly constant in ANY subject.

    python -m pfbench.refilter --pool pool

A ROI sphere lying mostly outside the brain mask gives a flat or nearly flat time
series. Testing std > 0 is not enough: floating-point rounding can give a perfectly
flat column a tiny nonzero std. A column is unusable in a subject if its std is below
rel_tol times that subject's median ROI std. The same ROI set is kept for every
subject, roi_coords.csv is rewritten to match, and the cached subject table is removed
so the next make_batch recomputes it. Safe to run more than once.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def usable_rois(series, rel_tol: float = 1e-3) -> np.ndarray:
    stds = np.stack([np.asarray(s, dtype=np.float64).std(axis=0) for s in series])
    med = np.median(stds, axis=1, keepdims=True)
    return np.all(stds > rel_tol * med, axis=0)


def refilter(pool, rel_tol: float = 1e-3) -> int:
    pool = Path(pool)
    files = sorted((pool / "timeseries").glob("*.npy"))
    series = [np.load(f) for f in files]
    coords = pd.read_csv(pool / "roi_coords.csv")
    if len(coords) != series[0].shape[1]:
        raise SystemExit("roi_coords.csv does not match the time series; rebuild the pool")
    keep = usable_rois(series, rel_tol)
    for f, s in zip(files, series):
        np.save(f, s[:, keep])
    coords[keep].to_csv(pool / "roi_coords.csv", index=False)
    (pool / "subject_table.csv").unlink(missing_ok=True)
    meta_path = pool / "pool_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta.update(refilter_rel_tol=rel_tol, n_rois_kept=int(keep.sum()),
                n_rois_dropped_by_refilter=int(meta.get("n_rois_dropped_by_refilter", 0) + (~keep).sum()))
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"[refilter] kept {int(keep.sum())} of {len(keep)} ROIs; dropped {int((~keep).sum())}")
    return int((~keep).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="pool")
    ap.add_argument("--rel-tol", type=float, default=1e-3)
    a = ap.parse_args()
    refilter(a.pool, a.rel_tol)


if __name__ == "__main__":
    main()
