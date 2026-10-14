# Task: author one new fault class for planted-fault-bench

You are extending a benchmark that measures whether research agents catch real
methodological faults in neuroimaging analyses, without being told a fault may exist.
Read these files first, in this order:

1. `METHOD.md` (the design, the levels, the gates, and why clean controls matter)
2. `pfbench/fault_classes/base.py` (the interface you implement)
3. `pfbench/fault_classes/motion_group_confound.py` (the reference implementation)
4. `pfbench/gates.py` and `pfbench/reference.py` (how variants are accepted; read only)

## What to build

Implement the fault named at the end of this prompt as a new module in
`pfbench/fault_classes/`, and register it in `pfbench/fault_classes/__init__.py`.

Requirements, all mandatory:

- **Grounded in a documented error.** Set `documented_source` to the paper(s) where the
  field actually made and corrected this error. If you cannot name a real source, stop
  and say so instead of inventing one.
- **Real data only.** Variants must be drawn or derived from the pool in `pool/`. Do not
  synthesize signals unless the fault is inherently a processing error applied to real
  data (for example, a wrong pipeline setting), and say which in the module docstring.
- **A clean control and a faulty variant with a strength dial.** `sample()` must
  support `variant="clean"` and `variant="faulty"` with `strength` in (0, 1]. Group sizes
  and file structure must be identical between clean and faulty variants.
- **No giveaways.** Nothing in the materialized data may reveal the label: no extra
  files, no suspiciously round values, no differences in n, no original subject IDs.
- **A continuous strength axis.** Implement `strength_axis()` in natural units of the
  fault (as the motion class uses child minus adult mean FD in mm).
- **A concern regex and an examination regex.** `concern_regex` identifies an agent
  concern that names this fault. Also write the regex that identifies code evidence
  that the agent examined the relevant quantity.
- **If the oracle needs a new check**, extend `pfbench/reference.py` with a check that a
  careful analyst would apply without knowing the variant: it must run identically on
  clean and faulty data and never read labels. Keep the motion check working.

## Rules you must not break

- Do not edit `pfbench/gates.py` or anything under `template/tests/`. The gates and the
  verifier define the benchmark; a fault author must not grade their own work.
  (A `git diff` check runs after you finish.)
- Do not write a real batch. Only run dry runs:
  `python3 -m pfbench.make_batch --pool pool --out /tmp/dry --fault <name> --dry-run`
- Do not lower thresholds just to make gates pass. If a strength level rarely passes,
  report it; that is information, not a bug.

## Iterate until

A dry run with `--n-clean 20 --n-faulty 20` meets both quotas, and every strength level
you keep accepts at least 20% of attempts. Then run `python3 -m pytest -q selftest`.

## Final report (print at the end)

1. The module path, the documented source, and a three-sentence description of the fault.
2. The dry-run gate report, verbatim.
3. The two regexes that a human must add to `CONCERN_RE` and `EXAMINE_RE` in
   `template/tests/score.py` (you may not add them yourself).
4. Anything about the fault that might still be a giveaway, and anything you are unsure of.
