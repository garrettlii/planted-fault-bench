# Results

All entries report totals only. Per-task results (which task IDs were clean or faulty)
stay with the private batch.

## v1-plain: GPT-6.1 Sol, motion_group_confound (2026-10-16/17)

### Headline

On the same 40 trials, Sol's analysis separated faulty from clean tasks well, but its
self-reported caveats did not separate them at all.

| Detection response | Hits (faulty) | False alarms (clean) | d′ | c |
|---|---|---|---|---|
| Sol flags motion as affecting its conclusion (the verifier's measure) | 20/20 | 20/20 | 0.00 | −1.98 |
| Sol's final estimate moves away from the naive estimate by more than the tolerance (post hoc) | 20/20 | 3/20 | 2.95 | −0.51 |

Sol corrected for motion on every faulty task and left 17 of 20 clean tasks alone, yet it
reported motion as changing its conclusion on all 40. On clean tasks, motion correction
changed nothing, and Sol still called it decisive.

Practical implication: an agent's self-reported caveats are not a usable grading signal
here. Score from outputs and logs.

The behavior-based measure was chosen **after** seeing the flag result. Treat it as an
observation about this batch until it is fixed in the verifier in advance and confirmed
on a fresh batch.

### What was run

| | |
|---|---|
| Model | `gpt-6.1-sol`, reasoning effort `xhigh`, reasoning summaries `detailed` |
| Harness | Codex CLI 0.163.0 (`codex exec`) on macOS through `run_local.sh`, not Harbor |
| Sign-in | Stanford ChatGPT workspace, for all 40 trials including the reruns |
| Sandbox | `workspace-write`; approvals forced to `on-request` by the workspace policy |
| Codex config | separate `CODEX_HOME` with no plugins, hooks or personal config; every graded trial was audited for 0 hook events and 0 references to the answer files |
| Sol's Python | its own venv outside the repo (pinned numpy, scipy, pandas, nilearn) |
| Code | commit `f57029b9b3c6cd189c3fc455be748876f1225600`; batch generated 2026-10-16 20:32 PDT |
| Repeats | k = 1 |

Why not Harbor: the workspace policy forbids running Codex without its sandbox, which
Harbor's Codex adapter requires, and Codex's own sandbox cannot start inside Docker.

### Data and batch

- **Pool.** OpenNeuro ds000228 through nilearn: 155 subjects (122 children, 33 adults),
  Power-264 coordinates with 5 mm spheres, no denoising. 237 ROIs kept: 15 dropped as
  zero-variance at extraction, plus 12 more dropped as constant or near-constant in at
  least one subject (relative tolerance 1e-3). Sol reported those 12 during the pilot;
  the original filter had missed them.
- **Fault class.** `motion_group_confound` (Power et al. 2012). Groups of 24 children
  and 16 adults. Clean: both groups drawn from subjects with mean FD < 0.2 mm. Faulty: a
  fraction of the children swapped for children with mean FD ≥ 0.3 mm.
- **Truth**, from all low-motion subjects (36 children, 22 adults): child minus adult
  segregation −0.0130 (SE 0.0062, Welch p = 0.042). The claim "children > adults" is not
  supported; in motion-matched data, children trend toward less segregation.
- **Batch.** Seed 20261014; 20 clean and 20 faulty tasks.

| Strength | Gate pass rate | Faulty tasks | Reached L5 |
|---|---|---|---|
| 0.5 | 2/9 | 2 | 1 |
| 0.6 | 3/8 | 3 | 2 |
| 0.7 | 8/8 | 8 | 7 |
| 0.8 | 7/8 | 7 | 5 |

All 20 clean draws passed the gates. Rejected faulty draws mostly failed G1: the fault
did not flip the naive verdict.

### Other results

| | |
|---|---|
| Faulty levels | L5 15, L4 5 (4 failed the confidence check, Brier > 0.25; 1 failed the tolerance check) |
| Verdict correct | 40/40 (uninformative: the true verdict is the same on every task) |
| Estimate within tolerance of truth | clean 19/20, faulty 19/20 |
| Clean over-corrections | 3 (2 of them still within tolerance of the truth) |
| Mean stated confidence that the claim is true | clean 0.235, faulty 0.355 |
| Mean Brier | 0.115 |
| Verifier reward | 15/40 (every faulty L5; no clean task, because of the flag) |
| Median agent time | 6.4 min per task |
| Median tokens | about 70.5k per task (Codex "tokens used", including cached input) |

### Interruptions

- The workspace ran out of credits partway through the first pass. 18 tasks (10 clean,
  8 faulty) ended without running and were initially graded as L0. After confirming the
  cause in their logs, their grades were deleted and the tasks rerun under the same
  sign-in once credits returned.
- Between the first pass and the reruns, `run_local.sh` gained a check that skips
  grading and stops the loop on credit, rate-limit or interrupted runs. The change
  affects only when a run is skipped, not how Sol runs or is graded.
- Pilot (6 tasks, different seed). The Harbor attempt scored 0/6 because the workspace
  policy blocked every command, not because of Sol. The local attempt completed 2 of 6
  before interruptions: one faulty task at L5 and one clean false alarm.

### Caveats

1. The behavior-based measure is post hoc, and its threshold (2 × the reference SE)
   decides what counts as "moved".
2. One fault class and one claim, with the same true verdict on every task, so verdict
   accuracy and Brier say little.
3. Only strong faults (0.5 to 0.8; 15 of 20 at 0.7 or 0.8). Weaker faults did not flip
   the naive verdict and were rejected, so this batch cannot show where Sol misses.
4. 20 + 20 tasks, run once each.
5. "Clean" means both groups are below 0.2 mm mean FD with no significant difference,
   not identical motion. Sol sometimes reported a residual difference, which may be
   literally true.
6. Local macOS harness under a managed workspace policy, so not directly comparable to
   Harbor runs of other agents.
7. Several task IDs and labels from this batch came up in a chat conversation while
   debugging. Treat this batch as burned; evaluate future agents on a fresh batch.

### Next (v0.2)

- Fix estimate-based detection in the gates and verifier before generating the batch,
  which also admits weaker faults and makes a detection threshold estimable.
- Add a second claim whose effect survives motion control.
- Match clean controls more tightly (nearest-neighbor matching on mean FD).
- Run k ≥ 3, and the `--journal` ablation.

### Re-scored with the v0.2 verifier (2026-10-17)

Same 40 trials, re-scored with `pfbench.rescore` (no new runs). Reproduces the post hoc
numbers above: behavior hits 20/20, false alarms 3/20, d′ 2.95, c −0.51; flag d′ 0.00;
report consistency 0.575; rewards 30/40. Faulty levels under v0.2: L5 15, L4 4, L3 1.

## v2-plain prediction (written before the batch was generated)

Scoring v0.2, seed 20261018, GPT-6.1 Sol, same harness as v1-plain. Prediction: behavior
d′ ≥ 1.5 and flag d′ ≤ 0.5, i.e. the say/do gap from v1-plain replicates on fresh tasks.
Either number landing on the other side counts as a failed replication.
