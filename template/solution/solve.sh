#!/bin/bash
# Reference (oracle) solution. Must reach level 5 on faulty variants and a correct
# rejection on clean ones; make_batch only ships variants where it does.
set -euo pipefail
OUTPUT_DIR="${OUTPUT_DIR:-/app/output}"
TASK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$OUTPUT_DIR" /app/analysis
cp -r "$TASK_DIR/solution/oracle/pfbench" /app/analysis/
cd /app/analysis
python3 -m pfbench.reference --data /app/data --out "$OUTPUT_DIR"
