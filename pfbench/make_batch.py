"""Generate a private batch of Harbor tasks from a data pool.

    python -m pfbench.make_batch --pool pool --out private_batch/v1 \
        --fault motion_group_confound --n-clean 20 --n-faulty 20 --seed 20261014

Deterministic given (pool, fault class, seed). Each candidate variant is drawn with its
own RNG stream, gated (see gates.py), and only accepted variants are written. Task IDs
are assigned in a shuffled order, so an ID says nothing about the label. The label lives
only in tests/variant_label.json and the batch-level MANIFEST.private.json.

Publish: this code, the fault classes, the template. Keep private: the batch directory.
"""
from __future__ import annotations

import argparse
import json
import shutil
import string
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from . import fault_classes, gates
from .analysis import group_effect, subject_table
from .reference import analyze

REPO = Path(__file__).resolve().parent.parent
SCORING_VERSION = "0.2"
TEMPLATE = REPO / "template"


def pool_table(pool: Path) -> pd.DataFrame:
    cache = pool / "subject_table.csv"
    if cache.exists():
        return pd.read_csv(cache)
    print(f"[make_batch] computing per-subject metrics for {pool} (cached afterwards)")
    t = subject_table(pool)
    t.to_csv(cache, index=False)
    return t


def draw(args, fault, table, truth):
    """Draw and gate candidates until quotas are met. Returns accepted + pass-rate report."""
    strengths = [float(x) for x in args.strengths.split(",")]
    want = {"clean": args.n_clean, "faulty": args.n_faulty}
    got, accepted, report = Counter(), [], Counter()
    i, faulty_tried = 0, 0
    while (got["clean"] < want["clean"] or got["faulty"] < want["faulty"]) and i < args.max_draws:
        variant = "clean" if (i % 2 == 0 and got["clean"] < want["clean"]) or \
            got["faulty"] >= want["faulty"] else "faulty"
        # cycle strengths over *attempts*, so a strength that rarely passes the gates
        # cannot stall the loop; its low acceptance shows up in the gate report instead
        strength = 0.0
        if variant == "faulty":
            strength = strengths[faulty_tried % len(strengths)]
            faulty_tried += 1
        rng = np.random.default_rng([args.seed, i])
        draw_ = fault.sample(rng, variant, strength)
        sub = table.set_index("subject").loc[draw_["subjects"]].reset_index()
        naive, _ = analyze(None, mode="naive", table=sub)
        ref, _ = analyze(None, mode="reference", table=sub)
        res = gates.check(variant, truth, naive, ref, sub, fault, fault_margin=args.fault_margin)
        key = f"{variant}@{strength:g}"
        report[key + ":tried"] += 1
        if res["pass"]:
            report[key + ":accepted"] += 1
            got[variant] += 1
            accepted.append(dict(index=i, variant=variant, strength=strength, draw=draw_,
                                 naive=naive, ref=ref, gate=res,
                                 strength_axis=fault.strength_axis(sub)))
        else:
            for g, ok in res["gates"].items():
                if not ok:
                    report[f"{key}:fail:{g}"] += 1
        i += 1
    return accepted, dict(sorted(report.items())), got


def write_task(task_dir: Path, a: dict, args, fault, table, truth, task_id: str):
    tpl_vars = {"TASK_ID": task_id, "BATCH": args.name,
                "JOURNAL_BLOCK": (TEMPLATE / "journal_block.md").read_text() if args.journal else ""}
    (task_dir / "environment").mkdir(parents=True)
    shutil.copy(TEMPLATE / "environment" / "Dockerfile", task_dir / "environment" / "Dockerfile")
    for name in ["instruction.md", "task.toml"]:
        src = string.Template((TEMPLATE / f"{name}.tmpl").read_text())
        (task_dir / name).write_text(src.safe_substitute(tpl_vars))
    rng = np.random.default_rng([args.seed, a["index"], 7])
    tokens = fault.materialize(Path(args.pool), task_dir / "environment" / "data",
                               a["draw"]["subjects"], table, rng)
    # solution: vendored oracle code (same code that gated the variant)
    sol = task_dir / "solution"
    shutil.copytree(TEMPLATE / "solution", sol)
    pkg = sol / "oracle" / "pfbench"
    pkg.mkdir(parents=True, exist_ok=True)
    for f in ["__init__.py", "analysis.py", "reference.py"]:
        shutil.copy(REPO / "pfbench" / f, pkg / f)
    # tests: verifier + the label (copied in by Harbor only at verification time)
    shutil.copytree(TEMPLATE / "tests", task_dir / "tests")
    label = dict(task_id=task_id, batch=args.name, fault_class=fault.name,
                 scoring_version=SCORING_VERSION, fault_margin=args.fault_margin,
                 naive_gap_in_tol=round(a["gate"]["naive_gap_in_tol"], 3),
                 variant=a["variant"], strength=a["strength"],
                 strength_axis=round(a["strength_axis"], 4),
                 k_swapped=a["draw"]["meta"].get("k_swapped"), journal=bool(args.journal),
                 truth={k: truth[k] for k in ("supported", "effect", "se", "p")},
                 recovery_tol=round(a["gate"]["recovery_tol"], 6),
                 naive={k: a["naive"][k] for k in ("claim_supported", "effect_estimate")},
                 reference={k: a["ref"][k] for k in ("claim_supported", "effect_estimate")},
                 seed=[args.seed, a["index"]], documented_source=fault.documented_source)
    (task_dir / "tests" / "variant_label.json").write_text(json.dumps(label, indent=2))
    return label, tokens


def end_to_end_check(task_dir: Path, label: dict, fault):
    """Re-run the oracle on the materialized files: must match what was gated."""
    v, _ = analyze(task_dir / "environment" / "data", mode="reference")
    ok = (v["claim_supported"] == label["reference"]["claim_supported"] and
          abs(v["effect_estimate"] - label["reference"]["effect_estimate"]) < 1e-9 and
          gates.moved(v["effect_estimate"], label["naive"]["effect_estimate"],
                      label["recovery_tol"]) == (label["variant"] == "faulty"))
    if not ok:
        raise RuntimeError(f"materialized oracle disagrees with gated oracle in {task_dir}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fault", default="motion_group_confound")
    ap.add_argument("--n-clean", type=int, default=20)
    ap.add_argument("--n-faulty", type=int, default=20)
    ap.add_argument("--strengths", default="0.3,0.4,0.5,0.6,0.7,0.8")
    ap.add_argument("--fault-margin", type=float, default=gates.FAULT_MARGIN,
                    help="G1: faulty naive estimate must sit > margin x tol from truth "
                         "(>= 2 guarantees that correct recovery counts as detection)")
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--max-draws", type=int, default=2000)
    ap.add_argument("--name", default=None, help="batch name (default: out dir name)")
    ap.add_argument("--journal", action="store_true", help="require a decision log (decisions.md)")
    ap.add_argument("--dry-run", action="store_true", help="gate only; print pass rates")
    ap.add_argument("--allow-synthetic", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    args.name = args.name or Path(args.out).name

    fault = fault_classes.get(args.fault)
    synthetic = (Path(args.pool) / "SYNTHETIC_DO_NOT_EVALUATE").exists()
    if synthetic and not args.dry_run and not args.allow_synthetic:
        sys.exit("pool is SYNTHETIC (mock); pass --allow-synthetic for smoke tests only")
    table = pool_table(Path(args.pool))
    summary = fault.setup(table)
    t = group_effect(fault.truth_subset(table))
    truth = dict(supported=t["supported"], effect=t["effect"], se=t["se"], p=t["p"],
                 n_child=t["n_child"], n_adult=t["n_adult"])
    print(f"[make_batch] fault={fault.name} pool={summary}")
    print(f"[make_batch] truth: supported={truth['supported']} effect={truth['effect']:.4f} "
          f"p={truth['p']:.3g} (n={truth['n_child']}+{truth['n_adult']})")

    accepted, report, got = draw(args, fault, table, truth)
    print("[make_batch] gate report:\n" + "\n".join(f"  {k}: {v}" for k, v in report.items()))
    short = {k: args.__dict__[f"n_{k}"] - got[k] for k in ("clean", "faulty") if got[k] < args.__dict__[f"n_{k}"]}
    if short:
        print(f"[make_batch] WARNING: quota not met {short}; see gate report (tune fault "
              f"parameters or --strengths)", file=sys.stderr)
    if args.dry_run:
        return 0

    out = Path(args.out)
    if out.exists():
        sys.exit(f"{out} exists; refusing to overwrite a batch")
    out.mkdir(parents=True)
    rng = np.random.default_rng([args.seed, 999])
    ids = rng.choice(np.arange(1000, 10000), size=len(accepted), replace=False)
    manifest, checked = [], set()
    for a, num in zip(accepted, ids):
        task_id = f"PF-{fault.name.split('_')[0].upper()}-{num}"
        label, _ = write_task(out / task_id, a, args, fault, table, truth, task_id)
        if a["variant"] not in checked:
            end_to_end_check(out / task_id, label, fault)
            checked.add(a["variant"])
        manifest.append(label)
    (out / "MANIFEST.private.json").write_text(json.dumps(manifest, indent=2))
    (out / "batch_report.json").write_text(json.dumps(
        dict(batch=args.name, fault=fault.name, seed=args.seed, pool_summary=summary,
             truth=truth, gate_report=report, accepted=dict(got), journal=args.journal,
             scoring_version=SCORING_VERSION, fault_margin=args.fault_margin,
             synthetic_pool=synthetic), indent=2))
    print(f"[make_batch] wrote {len(accepted)} tasks to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
