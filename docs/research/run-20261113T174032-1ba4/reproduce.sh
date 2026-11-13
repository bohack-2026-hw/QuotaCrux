#!/usr/bin/env bash
# Reproduce run-20261113T174032-1ba4 (C-01). Runs from the repository's backend/ directory.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$(git -C "$HERE" rev-parse --show-toplevel)/backend"
uv run routeevo tasks build >/dev/null   # frozen task packages, hashes checked against tasks/lock.json
# 1. Re-check the delivered program on the hidden final dataset (same evaluator, fresh containers)
uv run routeevo check C-01 "$HERE/best.py" --dataset final
# 2. Re-run the whole research loop with the same configuration (real models; replies vary between calls):
# uv run routeevo run C-01 --mode eval --snapshot v6
