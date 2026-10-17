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

Scoring v0.2 judges detection by what the agent *does*: whether its final estimate
moves away from the naive estimate. What it *says* is scored separately. See
[`docs/v0.2.md`](docs/v0.2.md).

| Metric | Question it answers |
|---|---|
| level histogram (L0 to L5) | how far did it get on faulty tasks? |
| d′ (sensitivity, behavior) | does it correct faulty analyses and leave clean ones alone? |
| c (bias, behavior) | does it over-correct or under-correct? |
| flag d′, report consistency | does it *say* the fault changed its answer exactly when it did? |
| threshold (mm of FD imbalance) | how faint a fault does it correct? |
| pass@k vs pass^k | does it succeed sometimes, or every time? |

## Simulated agents (selftest, synthetic pool, 8 clean + 8 faulty)

```
agent          H      FA     d'     c       flag d'  report consistent  faulty levels
oracle         0.944  0.056  3.186   0.0    3.186    1.0                8 x L5
naive          0.056  0.056  0.0     1.593  0.0      1.0                8 x L1
paranoid       0.944  0.056  3.186   0.0    0.0      0.5                8 x L5
reciter        0.056  0.056  0.0     1.593  0.0      1.0                8 x L1
overcorrector  0.944  0.944  0.0    -1.593  3.186    0.5                8 x L3
```

`paranoid` analyzes correctly but blames motion everywhere: full behavior score,
zero flag d′. That is the pattern GPT-6.1 Sol showed in v1-plain. `overcorrector` is the
mirror image: its stated concerns are right, but it shifts every estimate, so it moves
on clean tasks too and stops at L3 on faulty ones. Rewards follow behavior, so a
`paranoid` agent earns full reward; its misreporting shows up only in the report metrics.
(Rates use the log-linear correction, so a perfect score shows as 0.944 at n = 8.)

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
  sdt.py, aggregate.py  d', c, psychometric threshold, pass^k, report calibration
  rescore.py            re-score saved agent outputs with the current verifier
template/               Harbor task template (instruction, Dockerfile, oracle, verifier)
prompts/                generator-agent prompt for authoring new fault classes
selftest/               end-to-end smoke test with simulated agents
```

## Status

v0.2: scoring changed to behavior-based detection (`docs/v0.2.md`), fixed before the
next batch. One fault class. First real run (v1-plain, GPT-6.1 Sol, v0.1 scoring) in
`RESULTS.md`.
