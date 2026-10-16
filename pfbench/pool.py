"""Build the real-data pool from OpenNeuro ds000228 (nilearn-pinned derivatives).

    python -m pfbench.pool --out pool [--data-dir ~/nilearn_data] [--n-subjects N]

Downloads (once, cached by nilearn) the fMRIPrep-preprocessed movie-watching data for
122 children + 33 adults, extracts Power-264 ROI time series (5 mm spheres, NO denoising),
and writes the pool layout that pfbench.analysis expects. ROIs with zero variance in any
subject (spheres falling outside the brain mask) are dropped for everyone.

The pool is derived open data and is not secret. What must stay private is the batch
built from it (which subjects went into which variant, and the labels).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEEP_CONF = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
             "framewise_displacement", "csf", "white_matter", "global_signal",
             *[f"a_comp_cor_{i:02d}" for i in range(6)]]


def prepare_pool(out: Path, data_dir: str | None = None, n_subjects: int | None = None):
    from nilearn import datasets
    from nilearn.maskers import NiftiSpheresMasker

    dev = datasets.fetch_development_fmri(n_subjects=n_subjects, reduce_confounds=False,
                                          data_dir=data_dir)
    pheno = pd.DataFrame(dev.phenotypic)
    rois = pd.DataFrame(datasets.fetch_coords_power_2011().rois)
    coords = rois[["x", "y", "z"]].to_numpy(float)
    masker = NiftiSpheresMasker(seeds=coords, radius=5.0, allow_overlap=True,
                                detrend=False, standardize=False, t_r=2.0)

    (out / "timeseries").mkdir(parents=True, exist_ok=True)
    (out / "confounds").mkdir(parents=True, exist_ok=True)
    series, rows = {}, []
    for func, conf_path, (_, p) in zip(dev.func, dev.confounds, pheno.iterrows()):
        sid = str(p["participant_id"]) if "participant_id" in p else Path(func).name.split("_")[0]
        ts = masker.fit_transform(func).astype(np.float32)
        conf = pd.read_csv(conf_path, sep="\t")
        conf[[c for c in KEEP_CONF if c in conf.columns]].to_csv(
            out / "confounds" / f"{sid}.tsv", sep="\t", index=False)
        series[sid] = ts
        rows.append({"subject": sid, "age": float(p["Age"]),
                     "group": str(p["Child_Adult"]).strip().lower()})
        print(f"[pool] {sid}: {ts.shape}")

    from .refilter import usable_rois
    keep = usable_rois(list(series.values()))
    for sid, ts in series.items():
        np.save(out / "timeseries" / f"{sid}.npy", ts[:, keep])
    pd.DataFrame(rows).to_csv(out / "participants.tsv", sep="\t", index=False)
    rois.loc[keep, ["x", "y", "z"]].to_csv(out / "roi_coords.csv", index=False)
    (out / "pool_meta.json").write_text(json.dumps(
        {"dataset": "ds000228", "atlas": "Power 2011, 5 mm spheres", "n_rois_kept": int(keep.sum()),
         "n_rois_dropped": int((~keep).sum()), "n_subjects": len(rows)}, indent=2))
    print(f"[pool] wrote {len(rows)} subjects, {int(keep.sum())} ROIs to {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="pool")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--n-subjects", type=int, default=None)
    a = ap.parse_args()
    prepare_pool(Path(a.out), a.data_dir, a.n_subjects)


if __name__ == "__main__":
    main()
