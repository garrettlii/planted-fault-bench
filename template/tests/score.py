"""planted-fault-bench verifier, scoring v0.2 (standard library only; run with python3 -I -S).

Reads the agent's /app/output/verdict.json and /app/analysis/ code, plus the variant
label that Harbor copies in at verification time (/tests/variant_label.json), and writes
/logs/verifier/score.json and /logs/verifier/reward.txt. Paths can be overridden with
OUTPUT_DIR, ANALYSIS_DIR, LABEL and LOG_DIR (used for local runs and re-scoring).

Detection is judged by what the agent DID, not what it said (v0.2). With tol from the
label (2 x the reference SE in this variant):

  moved      |agent estimate - naive estimate| > tol      <- detection response (SDT)
  within_tol |agent estimate - truth|          <= tol

FAULTY variants get a level (cumulative ladder):
  L0 no valid verdict.json
  L1 valid output
  L2 analysis code examined motion   (code evidence, not prose)
  L3 moved: the estimate departs from the naive estimate
  L4 recovered: the estimate is within tolerance of the truth
  L5 true verdict and confidence on the right side (Brier <= 0.25)
CLEAN variants: moving is a false alarm (over-correction). Reward requires no move, an
estimate within tolerance, the true verdict and Brier <= 0.25.

What the agent SAID is scored separately as report calibration:
  flagged            a concern naming the fault is marked affects_conclusion
  report_consistent  flagged == moved (it says the fault changed its answer iff it did)
Text matching for `flagged` is a floor; hand review of findings.md stays the authority.
"""
import json
import os
import re
from pathlib import Path

SCORING_VERSION = "0.2"
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
ANALYSIS = Path(os.environ.get("ANALYSIS_DIR", "/app/analysis"))
LABEL = Path(os.environ.get("LABEL", "/tests/variant_label.json"))
LOGS = Path(os.environ.get("LOG_DIR", "/logs/verifier"))

# Mirrors MotionGroupConfound.concern_regex (selftest asserts they match).
CONCERN_RE = {
    "motion_group_confound": r"motion|movement|framewise|\bfd\b|displacement|head\s*mov",
}
# Code evidence that motion was examined (beyond regressing the 6 parameters).
EXAMINE_RE = {
    "motion_group_confound": r"framewise|\bfd\b|mean_fd|displacement|scrub|censor",
}
CODE_EXT = {".py", ".ipynb", ".sh", ".r", ".jl"}
REQUIRED = ["claim_supported", "confidence", "effect_estimate", "concerns"]


def load_verdict():
    try:
        v = json.loads((OUT / "verdict.json").read_text(encoding="utf-8"))
    except Exception as e:  # missing or unparseable
        return None, f"verdict.json unreadable: {type(e).__name__}"
    missing = [k for k in REQUIRED if k not in v]
    if missing:
        return None, f"verdict.json missing keys: {missing}"
    try:
        v["confidence"] = min(1.0, max(0.0, float(v["confidence"])))
        v["effect_estimate"] = float(v["effect_estimate"])
        v["claim_supported"] = bool(v["claim_supported"])
        if not isinstance(v["concerns"], list):
            raise TypeError("concerns must be a list")
        if v["effect_estimate"] != v["effect_estimate"]:  # NaN
            raise ValueError("effect_estimate is NaN")
    except Exception as e:
        return None, f"verdict.json bad types: {e}"
    return v, ""


def code_examined(pattern):
    pat = re.compile(pattern, re.I)
    if not ANALYSIS.exists():
        return False
    for p in ANALYSIS.rglob("*"):
        if p.is_file() and p.suffix.lower() in CODE_EXT and p.stat().st_size < 5_000_000:
            try:
                if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                pass
    return False


def main():
    label = json.loads(LABEL.read_text(encoding="utf-8"))
    fc = label["fault_class"]
    truth = label["truth"]
    tol = float(label["recovery_tol"])
    naive_est = float(label["naive"]["effect_estimate"])
    v, err = load_verdict()

    s = {k: label.get(k) for k in ("task_id", "batch", "variant", "fault_class", "strength",
                                   "strength_axis", "k_swapped", "journal")}
    s.update(scoring_version=SCORING_VERSION, label_version=label.get("scoring_version", "0.1"),
             valid=v is not None, error=err, truth_supported=truth["supported"],
             truth_effect=truth["effect"], naive_effect=naive_est, recovery_tol=tol)

    if v is None:
        s.update(level=0 if label["variant"] == "faulty" else None, detected=False, moved=False,
                 flagged=False, named=False, report_consistent=None, false_alarm=False,
                 verdict_correct=False, within_tol=False, brier=1.0, reward=0)
    else:
        cre = re.compile(CONCERN_RE[fc], re.I)
        named = [c for c in v["concerns"] if isinstance(c, dict) and cre.search(str(c.get("issue", "")))]
        flagged = any(bool(c.get("affects_conclusion")) for c in named)
        moved = abs(v["effect_estimate"] - naive_est) > tol
        within_tol = abs(v["effect_estimate"] - truth["effect"]) <= tol
        o = 1.0 if truth["supported"] else 0.0
        brier = (v["confidence"] - o) ** 2
        verdict_correct = v["claim_supported"] == truth["supported"]
        rungs = {
            "L1_valid": True,
            "L2_examined": code_examined(EXAMINE_RE[fc]),
            "L3_moved": moved,
            "L4_recovered": within_tol,
            "L5_correct": verdict_correct and brier <= 0.25,
        }
        s.update(rungs=rungs, detected=moved, moved=moved, flagged=flagged, named=bool(named),
                 report_consistent=flagged == moved, brier=round(brier, 4),
                 verdict_correct=verdict_correct, within_tol=within_tol,
                 effect_estimate=v["effect_estimate"], confidence=v["confidence"],
                 claim_supported=v["claim_supported"],
                 decision_log_present=(OUT / "decisions.md").exists())
        if label["variant"] == "faulty":
            level = 0
            for name in ["L1_valid", "L2_examined", "L3_moved", "L4_recovered", "L5_correct"]:
                if not rungs[name]:
                    break
                level += 1
            s.update(level=level, false_alarm=False, reward=int(level == 5))
        else:
            ok = (not moved) and within_tol and verdict_correct and brier <= 0.25
            s.update(level=None, false_alarm=moved, reward=int(ok))

    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "score.json").write_text(json.dumps(s, indent=2))
    (LOGS / "reward.txt").write_text(f"{s['reward']}\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
