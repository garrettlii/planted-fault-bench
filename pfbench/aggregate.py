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
  errored                    trials that produced no verifier score (excluded above)
  agent minutes, tokens, $   median agent wall time, median tokens, total cost
                             (from Harbor's per-trial result.json, when present)
Use --json to write the table for plotting.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

from .sdt import dprime_c, threshold


def _seconds(timing) -> float | None:
    try:
        a = datetime.fromisoformat(timing["started_at"])
        b = datetime.fromisoformat(timing["finished_at"])
        return (b - a).total_seconds()
    except (TypeError, KeyError, ValueError):
        return None


def load(dir_: Path) -> tuple[list[dict], list[dict]]:
    """Return (scored trials, errored trials).

    A Harbor trial directory holds result.json and verifier/score.json. Trials that
    crashed before grading have no score.json; they are reported, never silently
    dropped. Directories without result.json (the selftest) are read from score.json.
    """
    trial_dirs = {p.parent.parent for p in dir_.rglob("verifier/score.json")}
    for r in dir_.rglob("result.json"):
        try:
            if "trial_name" in json.loads(r.read_text()):
                trial_dirs.add(r.parent)
        except (OSError, ValueError):
            pass
    scored, errored = [], []
    for d in sorted(trial_dirs):
        res = {}
        if (d / "result.json").exists():
            res = json.loads((d / "result.json").read_text())
        ctx = res.get("agent_result") or {}
        meta = {
            "trial_name": res.get("trial_name", d.name),
            "agent_seconds": _seconds(res.get("agent_execution")),
            "tokens": (ctx.get("n_input_tokens") or 0) + (ctx.get("n_output_tokens") or 0)
            if ctx.get("n_input_tokens") is not None else None,
            "cost_usd": ctx.get("cost_usd"),
            "verifier_mode": res.get("verifier_environment_mode"),
            "exception": (res.get("exception_info") or {}).get("exception_type"),
            "agent_name": (res.get("agent_info") or {}).get("name"),
        }
        score = d / "verifier" / "score.json"
        if score.exists():
            scored.append({**json.loads(score.read_text()), **meta})
        else:
            errored.append(meta)
    return scored, errored


def _median(xs):
    xs = [x for x in xs if x is not None]
    return float(np.median(xs)) if xs else None


def summarize(trials: list[dict], errored: list[dict] | None = None) -> dict:
    errored = errored or []
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
        "errored": len(errored),
        "error_types": dict(Counter(e["exception"] or "no score" for e in errored)),
        "agent_min_median": (round(m / 60, 1) if (m := _median(
            [t.get("agent_seconds") for t in trials])) is not None else None),
        "suspiciously_fast": sum(1 for t in trials if t.get("agent_name") != "oracle"
                                 and t.get("agent_seconds") is not None and t["agent_seconds"] < 60),
        "tokens_median": (int(m) if (m := _median([t.get("tokens") for t in trials])) is not None
                          else None),
        "cost_usd_total": (round(sum(c), 2) if (c := [t["cost_usd"] for t in trials + errored
                                                      if t.get("cost_usd") is not None]) else None),
        "shared_verifier_trials": sum(1 for t in trials if t.get("verifier_mode") == "shared"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--run", action="append", required=True, help="LABEL=DIR")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    table = {}
    for spec in a.run:
        label, d = spec.split("=", 1)
        table[label] = summarize(*load(Path(d)))
    w = max(len(k) for k in table) + 2
    for cols in (["trials", "H", "FA", "dprime", "c", "mean_level_faulty", "mean_brier",
                  "pass_at_k", "pass_hat_k"],
                 ["errored", "threshold_mm", "agent_min_median", "tokens_median",
                  "cost_usd_total", "suspiciously_fast"]):
        print("agent".ljust(w) + "".join(c.rjust(18) for c in cols))
        for label, s in table.items():
            print(label.ljust(w) + "".join(str(s[c]).rjust(18) for c in cols))
        print()
    for label, s in table.items():
        print(f"{label}: faulty levels {s['level_hist']}  (k per task: {s['k_per_task']})")
        if s["errored"]:
            print(f"  {s['errored']} trial(s) produced no score: {s['error_types']}")
        if s["suspiciously_fast"]:
            print(f"  {s['suspiciously_fast']} scored trial(s) ran under 60 s: check credentials/quota")
        if s["shared_verifier_trials"]:
            print(f"  WARNING: {s['shared_verifier_trials']} trial(s) graded in the agent's own "
                  f"container; regenerate the batch with the current template")
    if a.json:
        Path(a.json).write_text(json.dumps(table, indent=2))
    return table


if __name__ == "__main__":
    main()
