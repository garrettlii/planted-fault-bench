# Method

## The idea in one line

A trap measures one detection. This benchmark measures the detector: whether an agent
can tell a faulty analysis setting from a clean one, how faint a fault it can catch, and
how far it gets once it does.

## Variants with ground truth by construction

Each task is drawn from a real data pool (OpenNeuro ds000228). A fault class defines:

- a **clean** variant (the negative control), and
- a **faulty** variant at a chosen **strength**,

with identical structure, so the agent cannot tell which it got without doing the
science. Because the generator chose the variant, the ground truth is known exactly.
That avoids the failure mode that retired SWE-bench Verified and SWE-bench Pro: tests
that were wrong about what the right answer is.

Fault class 1, `motion_group_confound`, replays Power et al. (2012): the child group is
partly made of high-motion children, which inflates short-range connectivity and fakes a
developmental effect. All data are real; the fault is which subjects are sampled.

## Levels (faulty variants)

| Level | Meaning | Evidence |
|---|---|---|
| L0 | No valid output | `verdict.json` missing or malformed |
| L1 | Ran the analysis | valid verdict |
| L2 | Examined the relevant quantity | analysis code under `/app/analysis` (not prose) |
| L3 | Noticed | a concern names the fault |
| L4 | Diagnosed | that concern is marked `affects_conclusion` |
| L5 | Correct | true verdict, estimate within tolerance, confidence on the right side |

Levels are cumulative: naming motion from memory without code evidence of a check stops
at L1. Clean variants are scored as correct rejection or false alarm, plus verdict checks.

## Summary statistics

- **Sensitivity d′ and bias c** on the detection response (L4 condition, all variants).
  An agent that always blames the fault gets d′ = 0 and c < 0; one that never does gets
  d′ = 0 and c > 0. Accuracy alone hides both (see the selftest table in README).
- **Threshold**: the fault strength (here, child minus adult mean FD in mm) at which the
  agent detects the fault half the time, from a logistic fit. This is how you say
  "agent A catches a 0.06 mm motion imbalance; agent B needs 0.15 mm".
- **pass@k vs pass^k** per task over k trials: any trial rewarded vs every trial rewarded.
- **Brier score** of the stated confidence in the claim (see limitation 1).

## Gates (pfbench/gates.py)

A drawn variant ships only if:

- **G1, the fault matters.** Faulty: the naive pipeline reaches the wrong verdict.
  Clean: it reaches the right one.
- **G2, the fault is fair.** The reference pipeline flags the fault iff the variant is
  faulty, reaches the true verdict, and lands within 2 SE of the true effect.
- **G3, no giveaway.** Same group sizes; random subject tokens; shuffled order.

The gate report is part of the result. On the synthetic pool, for example, strength 1.0
fails G2 every time: with every child high-motion, no motion-matched comparison exists,
so even the oracle cannot recover the truth. The honest answer there is "cannot be
determined", which v0.1 does not yet score (limitation 5).

## Publishing without burning the test

Public: this repo (method, fault classes, generator, verifier, template).
Private: every generated batch (`private_batch/`, gitignored). Labels live only in each
task's `tests/variant_label.json`, which Harbor copies in at verification time, and in
the batch's `MANIFEST.private.json`. Training on the public fault classes is fine: it
teaches real checks, clean controls punish blanket suspicion, and held-out fault classes
(planned) measure judgment beyond the checklist.

## Verifier hardening

Berkeley RDI (April 2026) reached 100% on Terminal-Bench by trojaning the `curl` that
verifiers used to download test dependencies. This verifier downloads nothing, uses only
the standard library, and runs as `python3 -I -S`, so agent-planted `sitecustomize`,
`.pth` files and shadowed packages are ignored. The agent still runs as root in the same
container and could replace `python3` itself; trajectory review stays the final word.

## Known limitations of v0.1

1. **One truth per pool.** Every variant shares the same true verdict (here: not
   supported once motion is controlled), so "always say no" scores well on the verdict
   and the Brier score. d′ is immune to this; the verdict metrics are not. Fix: add a
   second claim whose effect survives motion control.
2. **Text matching is a floor.** Concern detection is a regex over short issue labels.
   Hand re-score or a separate judge reading `findings.md` and the trajectory decides.
3. **L2 is crude.** Any code mentioning FD counts, including using FD only as a regressor.
4. **One fault class.** Held-out classes (to measure transfer beyond the checklist) need
   at least three classes; the generator prompt exists to add them.
5. **No abstention verdict.** Unrecoverable variants are rejected rather than scored.
6. **The claim is famous.** Agents may recall the motion literature from the claim alone.
   The clean controls and the code-evidence rung exist to separate recall from checking.
7. **Asking for a decision log can change behavior.** Run `--journal` and plain batches
   with the same seed and compare, rather than assuming narration is neutral.
