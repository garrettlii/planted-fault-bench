#!/bin/bash
# Run one planted-fault-bench task with Sol through local Codex (ChatGPT workspace sign-in),
# grade it with the task's own verifier, and audit the log.
#   usage: bash run_local.sh private_batch/pilot/PF-MOTION-XXXX
set -uo pipefail
REPO="${REPO:-$HOME/planted-fault-bench}"
SOLVENV="${SOLVENV:-$HOME/pf-venv}"
export CODEX_HOME="${CODEX_HOME_BENCH:-$HOME/.codex-bench}"
export PATH="$SOLVENV/bin:$PATH"

T="$(cd "$1" && pwd)" || { echo "no such task: $1"; exit 1; }
ID="$(basename "$T")"
W="$HOME/pf-runs/$ID"
S="$HOME/pf-runs/scores/$ID"
rm -rf "$W" "$S"; mkdir -p "$W/output" "$W/analysis" "$S/verifier"
cp -R "$T/environment/data" "$W/data"
sed -e 's#/app/data#./data#g; s#/app/output#./output#g; s#/app/analysis#./analysis#g' \
  "$T/instruction.md" > "$W/instruction.md"
cd "$W" && git init -q

echo "== $ID: Sol working (log: $W/codex.log)"
start=$(date +%s)
codex exec -m gpt-6.1-sol -c model_reasoning_effort=xhigh -c model_reasoning_summary=detailed \
  --sandbox workspace-write "$(cat instruction.md)" < /dev/null > codex.log 2>&1
secs=$(( $(date +%s) - start )); echo "$secs" > "$S/agent_seconds.txt"
if grep -q "ERROR: .*\(out of credits\|usage limit\|rate limit\|at capacity\)\|turn interrupted" "$W/codex.log"; then
  rm -rf "$S"; echo "   NOT RUN (credits, limit, or interrupted): no grade recorded; rerun later"; exit 3
fi

cd "$REPO"
OUTPUT_DIR="$W/output" ANALYSIS_DIR="$W/analysis" LABEL="$T/tests/variant_label.json" \
  LOG_DIR="$S/verifier" "$REPO/.venv/bin/python" -I -S "$T/tests/score.py" > /dev/null

hooks=$(grep -c "hook:" "$W/codex.log")
peeks=$(grep -c "private_batch\|variant_label\|MANIFEST" "$W/codex.log")
"$REPO/.venv/bin/python" - "$S/verifier/score.json" "$secs" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
print(f"   {s['variant']:6}  valid={s['valid']}  level={s['level']}  detected={s['detected']}  "
      f"reward={s['reward']}  agent={int(sys.argv[2]) // 60} min {s['error']}")
EOF
if [ "$hooks" -ne 0 ] || [ "$peeks" -ne 0 ]; then
  mv "$S/verifier" "$S/verifier.EXCLUDED"
  echo "   EXCLUDED: hooks fired=$hooks, answer-folder mentions=$peeks (both must be 0)"
fi
