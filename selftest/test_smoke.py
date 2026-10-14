"""End-to-end smoke test on the SYNTHETIC pool (no downloads, no Docker, no Harbor).

Builds a mock pool and a batch, then plays four simulated "agents" through every task,
scoring each with the real verifier (run exactly as test.sh runs it: python3 -I -S):

  oracle    the reference pipeline                      -> high d', reaches L5
  naive     common-practice pipeline, never checks FD   -> misses every fault (d' ~ 0)
  paranoid  always blames motion, always motion-matches -> catches faults AND false-alarms
  reciter   names motion from memory, never checks data -> stalls at L1 (no code evidence)

    pytest -q selftest
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pfbench import aggregate, make_batch, mock_pool  # noqa: E402
from pfbench.fault_classes import REGISTRY  # noqa: E402
from pfbench.reference import analyze  # noqa: E402


def _write(out: Path, analysis: Path, verdict: dict, code: str):
    out.mkdir(parents=True, exist_ok=True)
    analysis.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(json.dumps(verdict))
    (out / "findings.md").write_text("simulated\n")
    (analysis / "analysis.py").write_text(code)


def play(agent: str, task: Path, out: Path, analysis: Path):
    data = task / "environment" / "data"
    if agent == "oracle":
        v, _ = analyze(data, mode="reference")
        _write(out, analysis, v, "fd = framewise_displacement(conf)  # motion check\n")
    elif agent == "naive":
        v, _ = analyze(data, mode="naive")
        _write(out, analysis, v, "clean(ts, confounds=conf[['trans_x','rot_x']])\n")
    elif agent == "paranoid":
        v, _ = analyze(data, mode="reference")
        v = dict(v, concerns=[{"issue": "head motion likely drives the group effect",
                               "affects_conclusion": True}])
        _write(out, analysis, v, "fd = framewise_displacement(conf)\n")
    elif agent == "reciter":
        v, _ = analyze(data, mode="naive")
        v = dict(v, concerns=[{"issue": "motion is a known confound in developmental fMRI",
                               "affects_conclusion": False}])
        _write(out, analysis, v, "clean(ts, confounds=conf[['trans_x','rot_x']])\n")


def score(task: Path, out: Path, analysis: Path, logs: Path):
    env = dict(os.environ, OUTPUT_DIR=str(out), ANALYSIS_DIR=str(analysis),
               LABEL=str(task / "tests" / "variant_label.json"), LOG_DIR=str(logs))
    subprocess.run([sys.executable, "-I", "-S", str(task / "tests" / "score.py")],
                   env=env, check=True, capture_output=True)


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    root = tmp_path_factory.mktemp("pf")
    pool, batch, jobs = root / "pool", root / "batch", root / "jobs"
    mock_pool.make(pool)
    make_batch.main(["--pool", str(pool), "--out", str(batch), "--n-clean", "8",
                     "--n-faulty", "8", "--allow-synthetic"])
    tasks = sorted(p for p in batch.iterdir() if p.is_dir())
    for agent in ["oracle", "naive", "paranoid", "reciter"]:
        for t in tasks:
            work = root / "work" / agent / t.name
            play(agent, t, work / "output", work / "analysis")
            score(t, work / "output", work / "analysis", jobs / agent / t.name / "verifier")
    argv = []
    for agent in ["oracle", "naive", "paranoid", "reciter"]:
        argv += ["--run", f"{agent}={jobs / agent}"]
    table = aggregate.main(argv)
    return dict(table=table, batch=batch, tasks=tasks)


def test_labels_never_in_environment(results):
    for t in results["tasks"]:
        env_files = [p.name for p in (t / "environment").rglob("*")]
        assert "variant_label.json" not in env_files
        assert not re.search(r"clean|faulty", (t / "instruction.md").read_text(), re.I)


def test_oracle_separates_and_reaches_top(results):
    s = results["table"]["oracle"]
    assert s["false_alarms"] == 0 and s["hits"] == s["faulty"]
    assert s["dprime"] > 2.0 and s["level_hist"]["L5"] == s["faulty"]


def test_naive_never_detects(results):
    s = results["table"]["naive"]
    assert s["hits"] == 0 and s["false_alarms"] == 0 and abs(s["dprime"]) < 1e-9


def test_paranoid_has_no_sensitivity_and_liberal_bias(results):
    s = results["table"]["paranoid"]
    assert s["hits"] == s["faulty"] and s["false_alarms"] == s["clean"]
    assert abs(s["dprime"]) < 1e-9 and s["c"] < 0


def test_reciter_stalls_without_code_evidence(results):
    s = results["table"]["reciter"]
    assert s["level_hist"]["L1"] == s["faulty"]


def test_concern_regex_mirrored_in_verifier():
    src = (REPO / "template" / "tests" / "score.py").read_text()
    for name, cls in REGISTRY.items():
        assert f'"{name}": r"{cls.concern_regex}"' in src, f"score.py out of sync for {name}"
