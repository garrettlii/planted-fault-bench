# Running it

Each step is independent; stop after any one and inspect the output.

## 0. Install and smoke test (no downloads, about 4 minutes)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest -q selftest          # synthetic pool, four simulated agents
```

## 1. Build the real pool (once; needs internet)

```bash
python3 -m pfbench.pool --out pool --data-dir ~/nilearn_data
```

Downloads ds000228 through nilearn (cached), extracts Power-264 series, writes `pool/`.

## 2. Dry-run the gates on real data

```bash
python3 -m pfbench.make_batch --pool pool --out /tmp/dry --n-clean 20 --n-faulty 20 --dry-run
```

Read the gate report before anything else. It tells you, per strength, how often the
fault fooled the naive pipeline and how often the oracle recovered the truth. If the real
pool has fewer low-motion children than the defaults expect, the fault class clips group
sizes and prints them; tune `fd_match`, `fd_high`, `n_child`, `n_adult` in
`pfbench/fault_classes/motion_group_confound.py`.

## 3. Generate two private batches with the same seed

```bash
python3 -m pfbench.make_batch --pool pool --out private_batch/v1-plain   --seed 20261014
python3 -m pfbench.make_batch --pool pool --out private_batch/v1-journal --seed 20261014 --journal
```

Same variants, same task IDs; the only difference is that `--journal` asks the agent to
keep `/app/output/decisions.md`. That makes the decision log an ablation you can measure.

## 4. Check every task with the oracle

```bash
for t in private_batch/v1-plain/PF-*/; do
  harbor run -p "$t" -a oracle -o jobs/oracle -k 1 -y
done
python3 -m pfbench.aggregate --run "oracle=jobs/oracle"
```

Expect level 5 on every faulty task and zero false alarms. Before trusting any agent
run, also confirm that your Harbor version copies `tests/` in only at verification time
(if the agent can read `tests/variant_label.json`, the label leaks).

## 5. Run agents (k = 3 for reliability)

Claude (Claude Code):

```bash
for t in private_batch/v1-plain/PF-*/; do
  harbor run -p "$t" -a claude-code -m claude-opus-5-5 -o jobs/claude-plain -k 3 -y
done
```

GPT Sol (Codex), both batches:

```bash
for b in plain journal; do
  for t in private_batch/v1-$b/PF-*/; do
    harbor run -p "$t" -a codex -m gpt-6.1-sol --ak reasoning_effort=xhigh -o jobs/sol-$b -k 3 -y
  done
done
```

Confirm the exact model ID with your Codex install before a full run. On reasoning:
OpenAI does not expose a reasoning model's raw chain of thought. What you can collect is
(a) `decisions.md` from the journal batch, which is the model's own account, (b) any
reasoning summaries your Codex configuration logs (Codex has a reasoning-summary
setting; check whether Harbor's codex adapter passes it through), and (c) the trajectory
of commands it actually ran. Score from (c); treat (a) and (b) as self-report.

## 6. Compare

```bash
python3 -m pfbench.aggregate \
  --run "Claude Opus 5.5=jobs/claude-plain" \
  --run "Sol (plain)=jobs/sol-plain" \
  --run "Sol (journal)=jobs/sol-journal" \
  --json jobs/summary.json
```

Then hand re-score the borderline trials (any L3 without L4, any false alarm) by
reading `findings.md`, `decisions.md` and the trajectory.

## 7. Author a new fault class with a Claude generator agent

Commit first so the grader check below is meaningful, then:

```bash
git add -A && git commit -m "before generator run"

FAULT_SPEC="Global signal regression dependence: the group difference appears or
reverses depending on whether GSR is applied (Murphy et al. 2009; Saad et al. 2012)."

claude -p "$(cat prompts/GENERATE_FAULT_CLASS.md)

FAULT TO IMPLEMENT: $FAULT_SPEC" \
  --model claude-opus-5-5 \
  --permission-mode acceptEdits \
  --allowedTools "Read" "Edit" "Write" "Bash(python3 -m pfbench*)" "Bash(python3 -m pytest*)" \
  --max-turns 80 \
  --output-format json > jobs/generator.json

# The generator may not touch the gates or the verifier:
git diff --exit-code -- pfbench/gates.py template/tests/ && echo "grader untouched"
```

Review the new module and its gate report yourself, copy the two regexes it reports into
`template/tests/score.py`, and rerun `pytest -q selftest`. Flags follow the Claude Code
CLI reference (https://code.claude.com/docs); check them against your installed version.
