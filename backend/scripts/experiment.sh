#!/usr/bin/env bash
# Full shared-core experiment, reproducible from a clean var/ directory.
#   1. rebuild the frozen task packages (hashes must match tasks/lock.json)
#   2. learn on A serially from v0; each run publishes a new snapshot
#   3. B: development comparison, v0 vs the learned snapshot, 3 repeats
#   4. C: final held-out comparison with the same frozen configuration
# Usage: scripts/experiment.sh [learn|compare-b|compare-c|all]
set -euo pipefail
cd "$(dirname "$0")/.."

step=${1:-all}
learned() { uv run python -c "from routeevo import db; print(db.one(\"SELECT snapshot_id FROM snapshots ORDER BY version DESC LIMIT 1\")['snapshot_id'])"; }

if [[ $step == all || $step == learn ]]; then
  uv run routeevo tasks build
  uv run routeevo learn A-01 A-02 A-03 A-04 A-05 A-06 --label "formal A learning"
fi
if [[ $step == all || $step == compare-b ]]; then
  uv run routeevo compare B-01 B-02 B-03 B-04 B-05 B-06 --a v0 --b "$(learned)" --repeats 3 --label "B dev comparison"
fi
if [[ $step == all || $step == compare-c ]]; then
  uv run routeevo compare C-01 C-02 C-03 C-04 C-05 C-06 --a v0 --b "$(learned)" --repeats 3 --label "C final held-out"
fi
