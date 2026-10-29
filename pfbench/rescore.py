"""Re-score saved agent outputs with the current verifier (template/tests/score.py).

    python -m pfbench.rescore --batch private_batch/v1-plain --runs ~/benchmarks/pf/pf-runs --out ~/benchmarks/pf/pf-runs-rescored

For every task in --batch that has a work folder under --runs (as written by
run_local.sh: <runs>/<TASK_ID>/output and /analysis), run the current verifier against
that task's label and write <out>/<TASK_ID>/verifier/score.json, copying
agent_seconds.txt when present. The agent outputs are only read, never changed, so
re-scoring costs nothing and can be repeated whenever the verifier changes.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    batch, runs, out = Path(a.batch), Path(a.runs).expanduser(), Path(a.out).expanduser()
    verifier = REPO / "template" / "tests" / "score.py"
    done = missing = 0
    for task in sorted(p for p in batch.iterdir() if (p / "tests" / "variant_label.json").exists()):
        work = runs / task.name
        if not (work / "output").exists():
            missing += 1
            continue
        logs = out / task.name / "verifier"
        if logs.parent.exists():
            shutil.rmtree(logs.parent)
        logs.mkdir(parents=True)
        env = dict(os.environ, OUTPUT_DIR=str(work / "output"), ANALYSIS_DIR=str(work / "analysis"),
                   LABEL=str(task / "tests" / "variant_label.json"), LOG_DIR=str(logs))
        subprocess.run([sys.executable, "-I", "-S", str(verifier)], env=env, check=True,
                       capture_output=True)
        secs = runs / "scores" / task.name / "agent_seconds.txt"
        if secs.exists():
            shutil.copy(secs, logs.parent / "agent_seconds.txt")
        done += 1
    print(f"[rescore] re-scored {done} tasks into {out} ({missing} tasks had no saved outputs)")


if __name__ == "__main__":
    main()
