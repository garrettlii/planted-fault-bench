#!/bin/bash
# Verifier. Hardened against the exploit class Berkeley RDI used on Terminal-Bench /
# SWE-bench (April 2026): no downloads at verification time (no curl/pip/uvx the agent
# could have trojaned), stdlib-only Python run in isolated mode (-I) without the site
# module (-S), so agent-planted sitecustomize/.pth files and shadowed packages are ignored.
# Residual risk: the agent ran as root in this container and could replace python3
# itself. Human review of the trajectory remains the final authority.
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
python3 -I -S /tests/score.py
