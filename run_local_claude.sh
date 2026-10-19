#!/bin/bash
# Run one planted-fault-bench task with Claude (default Opus 5.5) through local Claude Code,
# signed in with your enterprise account, grade it with the task's own verifier, and audit
# the full trajectory.
#   usage: bash run_local_claude.sh private_batch/v2-plain/PF-MOTION-XXXX
# Exit code 3 = the run did not happen (sign-in, limits, capacity, sandbox unavailable):
# no grade is recorded, so a resume loop will retry it later.
set -uo pipefail
REPO="${REPO:-$HOME/planted-fault-bench}"
AGENT_VENV="${AGENT_VENV:-$HOME/pf-venv}"                          # same Python Sol used
export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR_BENCH:-$HOME/.claude-bench}"   # clean config
export ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_EFFORT_LEVEL="${EFFORT:-xhigh}"
MODEL="${MODEL:-claude-opus-5-5}"
RUNS="${RUNS:-$HOME/bench-claude}"                 # Claude's work folders
SCORES="${SCORES:-$HOME/bench-claude-scores}"      # grades: kept apart so the sandbox can deny it
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN   # use the sign-in, not a key
export PATH="$AGENT_VENV/bin:$PATH"
PY="$REPO/.venv/bin/python"

T="$(cd "$1" && pwd)" || { echo "no such task: $1"; exit 1; }
ID="$(basename "$T")"
W="$RUNS/$ID"
S="$SCORES/$ID"
rm -rf "$W" "$S"; mkdir -p "$W/output" "$W/analysis" "$S/verifier"
cp -R "$T/environment/data" "$W/data"
sed -e 's#/app/data#./data#g; s#/app/output#./output#g; s#/app/analysis#./analysis#g' \
  "$T/instruction.md" > "$W/instruction.md"
cd "$W" && git init -q

echo "== $ID: Claude working (trajectory: $W/trajectory.jsonl)"
start=$(date +%s)
claude -p "$(cat instruction.md)" --model "$MODEL" \
  --output-format stream-json --verbose \
  --permission-mode dontAsk \
  --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" \
  --disallowedTools "WebFetch" "WebSearch" \
  < /dev/null > trajectory.jsonl 2> claude.stderr
secs=$(( $(date +%s) - start )); echo "$secs" > "$S/agent_seconds.txt"

# Did the run actually happen? Read the init and final result events.
"$PY" - "$W/trajectory.jsonl" "$S/run_meta.json" <<'EOF'
import json, sys
init, result = {}, {}
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "system" and e.get("subtype") == "init":
        init = e
    if e.get("type") == "result":
        result = e
meta = {"model": init.get("model"), "permission_mode": init.get("permissionMode"),
        "api_key_source": init.get("apiKeySource"), "tools": init.get("tools"),
        "mcp_servers": init.get("mcp_servers"), "plugins": init.get("plugins"),
        "is_error": result.get("is_error", True), "subtype": result.get("subtype"),
        "num_turns": result.get("num_turns"), "duration_ms": result.get("duration_ms"),
        "total_cost_usd": result.get("total_cost_usd"), "usage": result.get("usage")}
json.dump(meta, open(sys.argv[2], "w"), indent=2)
sys.exit(0 if result and not meta["is_error"] else 3)
EOF
if [ $? -ne 0 ]; then
  rm -rf "$S"
  echo "   NOT RUN: no successful result from Claude Code (see $W/claude.stderr and the end of the trajectory); rerun later"
  exit 3
fi

cd "$REPO"
OUTPUT_DIR="$W/output" ANALYSIS_DIR="$W/analysis" LABEL="$T/tests/variant_label.json" \
  LOG_DIR="$S/verifier" "$PY" -I -S "$T/tests/score.py" > /dev/null

peeks=$(grep -c "private_batch\|variant_label\|MANIFEST\|pf-runs\|codex-bench\|bench-claude-scores" "$W/trajectory.jsonl")
extras=$("$PY" -c "import json,sys; m=json.load(open(sys.argv[1])); print(len(m.get('mcp_servers') or []) + sum(1 for x in (m.get('plugins') or []) if x.get('path') != 'builtin'))" "$S/run_meta.json")
"$PY" - "$S/verifier/score.json" "$secs" "$S/run_meta.json" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1])); m = json.load(open(sys.argv[3]))
print(f"   {s['variant']:6}  valid={s['valid']}  level={s['level']}  detected={s['detected']}  "
      f"reward={s['reward']}  agent={int(sys.argv[2]) // 60} min  model={m['model']} {s['error']}")
EOF
if [ "$peeks" -ne 0 ] || [ "$extras" -ne 0 ]; then
  mv "$S/verifier" "$S/verifier.EXCLUDED"
  echo "   EXCLUDED: answer-folder mentions=$peeks, MCP servers or add-on plugins loaded=$extras (both must be 0)"
fi
