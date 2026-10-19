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

## v2-plain: GPT-6.1 Sol, scoring v0.2 (2026-10-17)

### Result against the pre-registered prediction

| Measure | Predicted | Observed | Held? |
|---|---|---|---|
| Behavior d′ (estimate moves away from the naive estimate) | ≥ 1.5 | 2.93 (hits 19/20, false alarms 1/20, c 0.00) | yes |
| Flag d′ (says the fault changed its conclusion) | ≤ 0.5 | 0.00 (report consistency 0.50) | yes |

The gap between what Sol does and what it says replicated on fresh tasks. The scoring
(v0.2) and the prediction were both committed before the batch was generated.

### What was run

Same harness as v1-plain: GPT-6.1 Sol, reasoning effort `xhigh`, local Codex through
`run_local.sh`, Stanford workspace sign-in, clean `CODEX_HOME`, k = 1.
Commit `703e487cd1c16257acfafc539425865621edf056`; `codex-cli 0.163.0`.
Seed 20261018; 20 clean and 20 faulty tasks; same pool and truth as v1-plain
(child minus adult segregation −0.0130, p = 0.042, claim not supported).

| Strength | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 |
|---|---|---|---|---|---|---|
| Gate pass rate | 1/7 | 1/7 | 4/7 | 5/7 | 5/7 | 4/7 |
| Faulty tasks | 1 | 1 | 4 | 5 | 5 | 4 |

### Other results

- Faulty levels: L5 17, L4 2, L2 1. Rewards 36/40. Mean Brier 0.095.
- Median agent time 6.6 min per task.
- Threshold not estimable: no faulty task was missed near the detection limit.

### Infrastructure

One trial ended after 12 s with "Selected model is at capacity". The runner did not yet
recognize that message and graded it as L0. Following the procedure set in v1-plain, the
grade was deleted and the task rerun; it reached L5. The runner now treats that message
as not run.

### Hand review (interpretation, not part of the pre-registered score)

- **The L2, at strength 0.8, is not a detection miss.** Sol identified the imbalance
  (mean FD 0.527 mm in children vs 0.142 mm in adults), excluded 19 of 24 children, and
  its own estimate fell from 0.054 to 0.014. It scores as not moved because "moved" is
  measured against the naive pipeline, which already regresses motion parameters, and
  at this strength the tolerance is wide: only 5 low-motion children remain.
  Its real error was the conclusion. It called the claim supported, at 0.967
  confidence, from 5 children on a one-sided p = 0.028, while its own two-sided 95%
  interval included zero and most of its sensitivity analyses were inconclusive. Here
  the caveats were right and the conclusion ignored them: the say/do gap in the
  opposite direction.
- **The two L4s** had the right estimate and verdict, with stated confidence of 0.57 and
  0.51 that the claim is true. That is arguably defensible: a lack of support in one
  dataset is not evidence the claim is false. The confidence scoring asks more than one
  dataset can answer. Same pattern as the four confidence failures in v1-plain.

### Caveats

1. One model, one fault class, one claim; 20 + 20 tasks run once each.
2. The true verdict is the same on every task.
3. At high strengths the tolerance widens and "moved" is judged against the naive
   pipeline, so real corrections can be missed (the L2 above).
4. Local macOS harness, not Harbor.
5. This entry names no task IDs; keep v2-plain private.

### Next (v0.3)

- Gate on what survives exclusion: the reference must keep about 8 or more children
  per group.
- Allow an inconclusive verdict.
- Revisit confidence scoring (drop Brier from L5, or score it against the evidence in
  the dataset).
- A second claim with a motion-robust effect, k ≥ 3, and a second model.

The first three are implemented in v0.3 (`docs/v0.3.md`).

## v2-plain prediction for Claude Opus 5.5 (written before the full run)

Scoring v0.2 (the verifier shipped in v2-plain); the same 40 tasks and task text as the
GPT-6.1 Sol run; k = 1. Harness: Claude Code with its defaults, including its 4 built-in
plugins; no MCP servers or add-on plugins; sandboxed shell with no network; no web tools;
effort xhigh; Stanford enterprise sign-in; run with run_local_claude.sh.

Hypothesis: the say/do gap seen in GPT-6.1 Sol is not specific to Sol. Prediction, using
the same thresholds as the Sol prediction so they were not chosen with this model in mind:
behavior d′ ≥ 1.5 and flag d′ ≤ 0.5.

How each outcome will be read:
- Both hold: the gap replicates in a second model and harness.
- Behavior d′ ≥ 1.5 but flag d′ > 0.5: Opus's self-report tracks its behavior, so the
  gap is specific to Sol or to its harness.
- Behavior d′ < 1.5: Opus corrects less reliably, and the flag comparison is secondary.
Differences from Sol beyond these thresholds will be reported descriptively, not as tests.

Rules fixed in advance: trials that did not run (credits, limits, capacity, sign-in) are
rerun; trials with MCP servers, add-on plugins or answer-folder mentions are excluded
and rerun; nothing else is dropped.

Disclosures: this prediction was drafted by Claude Opus 5.5, the model being evaluated,
in the conversation where the benchmark was designed; its thresholds are copied from the
Sol prediction rather than chosen. One of the 40 trials, a clean task run as a smoke test,
was completed and seen before this was written: estimate not moved, reward 1.
