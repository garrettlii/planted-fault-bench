# planted-fault-bench

Does a research agent catch a real methodological fault it was never told about, and
can it tell a faulty setting from a clean one?

Each task is a real neuroimaging analysis (OpenNeuro ds000228, in Harbor /
terminal-bench format). Every run randomly gets either a **clean** variant or a
**faulty** variant with a planted fault at a chosen strength. The agent is asked only to
do the science. Because the fault was planted, ground truth is known exactly; because
clean controls exist, blanket suspicion is penalized; because the variant is drawn per
task from a private batch, publishing the method does not burn the test.

Builds on the trap tasks in
[brain-researcher-benchmark](https://github.com/brain-researcher/brain-researcher-benchmark):
same task format and the same un-cued judgment idea, turned from a single trap into a
measurement of the detector. Design details: [`METHOD.md`](METHOD.md). Commands:
[`RUN.md`](RUN.md).

## What you get per agent

| Metric | Question it answers |
|---|---|
| level histogram (L0 to L5) | how far did it get on faulty tasks? |
| d′ (sensitivity) | can it tell faulty from clean? |
| c (bias) | does it over-flag or under-flag? |
| threshold (mm of FD imbalance) | how faint a fault can it catch? |
| pass@k vs pass^k | does it succeed sometimes, or every time? |

## Simulated agents (selftest, synthetic pool, 8 clean + 8 faulty)

```
agent       H      FA     d'     c      mean level   pass^k
oracle      0.944  0.056  3.186  0.0    5.0          1.0
naive       0.056  0.056  0.0    1.593  1.0          0.5
paranoid    0.944  0.944  0.0   -1.593  5.0          0.5
reciter     0.056  0.056  0.0    1.593  1.0          0.5
```

`paranoid` always blames motion: it reaches L5 on every faulty task yet has zero
sensitivity, because it false-alarms on every clean one. `naive` gets half the tasks
"right" (the clean ones) with zero sensitivity. Neither accuracy nor level alone would
have shown either failure. `reciter` names motion from memory but never checks the data,
so it stops at L1. (Rates use the log-linear correction, so a perfect score shows as
0.944 at n = 8.)

## Layout

```
pfbench/
  analysis.py           shared connectivity / segregation / group-effect code
  reference.py          naive pipeline and reference (oracle) pipeline
  fault_classes/        base interface + motion_group_confound (Power et al. 2012)
  gates.py              acceptance gates G1-G3 (do not edit from a generator agent)
  make_batch.py         seeded variant generator -> private Harbor task directories
  pool.py               builds the real-data pool from ds000228 (needs internet once)
  mock_pool.py          SYNTHETIC pool for smoke tests only
  sdt.py, aggregate.py  d', c, psychometric threshold, pass^k
template/               Harbor task template (instruction, Dockerfile, oracle, verifier)
prompts/                generator-agent prompt for authoring new fault classes
selftest/               end-to-end smoke test with simulated agents
```

## Status

v0.1: one fault class, tested end to end on synthetic data only. Not yet run on the real
pool or with real agents. Read the limitations in `METHOD.md` before reporting numbers.
