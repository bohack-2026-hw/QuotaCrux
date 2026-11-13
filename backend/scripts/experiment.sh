#!/usr/bin/env bash
# Full experiment, reproducible from a clean var/ directory. Version 2 (current code) re-validates verified programs
# from experience before asking a model; version 1 used text experience only and is kept for reference.
#   1. rebuild the frozen task packages (hashes must match tasks/lock.json)
#   2. learn on A serially from v0, two rounds; each run publishes a new snapshot
#   3. B: development comparison, v0 vs the learned snapshot, 3 repeats
#   4. D: sealed held-out comparison with the same frozen configuration, run once
# Usage: scripts/experiment.sh [learn|compare-b|compare-d|all]
# Version 1 used: learn --label "formal A learning", then the B and C comparisons labelled "B dev comparison" and
# "C final held-out" (see docs/results.md section 3).
set -euo pipefail
cd "$(dirname "$0")/.."

step=${1:-all}
learned() { uv run python -c "from routeevo import db; print(db.one(\"SELECT snapshot_id FROM snapshots ORDER BY version DESC LIMIT 1\")['snapshot_id'])"; }

if [[ $step == all || $step == learn ]]; then
  uv run routeevo tasks build
  uv run routeevo snapshots activate v0 --reason "learn from empty experience"
  uv run routeevo learn A-01 A-02 A-03 A-04 A-05 A-06 --label "reuse A learning r1"
  uv run routeevo learn A-01 A-02 A-03 A-04 A-05 A-06 --label "reuse A learning r2"
fi
if [[ $step == all || $step == compare-b ]]; then
  uv run routeevo compare B-01 B-02 B-03 B-04 B-05 B-06 --a v0 --b "$(learned)" --repeats 3 --label "B dev comparison · reuse"
fi
if [[ $step == all || $step == compare-d ]]; then
  uv run routeevo compare D-01 D-02 D-03 D-04 D-05 D-06 --a v0 --b "$(learned)" --repeats 3 --label "D final held-out · reuse"
fi
