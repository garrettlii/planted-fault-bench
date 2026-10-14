"""Aggregate verifier score.json files into a per-agent comparison.

    python -m pfbench.aggregate --run "Claude Opus=jobs/claude" --run "GPT Sol=jobs/sol"

Each --run is LABEL=DIR; every score.json found under DIR (any depth) is one trial.
Prints, per agent:
  trials, faulty/clean counts
  H, FA, d', c               signal detection on the detection response
  level histogram (faulty)   where on the ladder each faulty trial stopped
  mean Brier                 calibration of the verdict
  threshold                  fault strength (child-adult mean FD, mm) at 50% detection
  pass@k / pass^k            per task: any trial rewarded / every trial rewarded
Use --json to write the table for plotting.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .sdt import dprime_c, threshold


def load(dir_: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(dir_.rglob("score.json"))]


def summarize(trials: list[dict]) -> dict:
    faulty = [t for t in trials if t["variant"] == "faulty"]
    clean = [t for t in trials if t["variant"] == "clean"]
    hits = sum(bool(t["detected"]) for t in faulty)
    fas = sum(bool(t["detected"]) for t in clean)
    sdt = dprime_c(hits, len(faulty), fas, len(clean))
    levels = Counter(int(t["level"]) for t in faulty)
    xs = [t["strength_axis"] for t in trials if t.get("strength_axis") is not None]
    ys = [float(bool(t["detected"])) for t in trials if t.get("strength_axis") is not None]
    by_task = defaultdict(list)
    for t in trials:
        by_task[t["task_id"]].append(int(t["reward"]))
    return {
        "trials": len(trials), "faulty": len(faulty), "clean": len(clean),
        "hits": hits, "false_alarms": fas,
        **{k: round(v, 3) for k, v in sdt.items()},
        "level_hist": {f"L{k}": levels.get(k, 0) for k in range(6)},
        "mean_level_faulty": round(float(np.mean([t["level"] for t in faulty])), 2) if faulty else None,
        "mean_brier": round(float(np.mean([t["brier"] for t in trials])), 3) if trials else None,
        "threshold_mm": (round(th, 3) if (th := threshold(xs, ys)) is not None else None),
        "pass_at_k": round(float(np.mean([max(r) for r in by_task.values()])), 3) if by_task else None,
        "pass_hat_k": round(float(np.mean([min(r) for r in by_task.values()])), 3) if by_task else None,
        "k_per_task": sorted({len(r) for r in by_task.values()}),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--run", action="append", required=True, help="LABEL=DIR")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    table = {}
    for spec in a.run:
        label, d = spec.split("=", 1)
        table[label] = summarize(load(Path(d)))
    cols = ["trials", "H", "FA", "dprime", "c", "mean_level_faulty", "mean_brier",
            "threshold_mm", "pass_at_k", "pass_hat_k"]
    w = max(len(k) for k in table) + 2
    print("agent".ljust(w) + "".join(c.rjust(18) for c in cols))
    for label, s in table.items():
        print(label.ljust(w) + "".join(str(s[c]).rjust(18) for c in cols))
    print()
    for label, s in table.items():
        print(f"{label}: faulty levels {s['level_hist']}  (k per task: {s['k_per_task']})")
    if a.json:
        Path(a.json).write_text(json.dumps(table, indent=2))
    return table


if __name__ == "__main__":
    main()
