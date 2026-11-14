#!/usr/bin/env bash
# Recheck frozen artifacts with Docker; no model requests.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$(git -C "$HERE" rev-parse --show-toplevel)/backend"
export ROUTEEVO_VAR_DIR="${ROUTEEVO_VAR_DIR:-$PWD/var/effibench-x-recheck}"

for problem in codeforces/2104A codeforces/2108A leetcode/3188 leetcode/3193; do
  uv run --extra benchmark routeevo tasks import-effibench "$problem" --split B --dev-cases 5 --case-limit 20
  name="${problem/\//-}"
  timing=()
  # c0 was checked for correctness only in the recorded experiment.
  if [[ $problem == codeforces/* ]]; then timing=(--no-timing); fi
  uv run routeevo check "ebx-$name-B-5-20" "$HERE/best/$name.py" --dataset final "${timing[@]}"
done
