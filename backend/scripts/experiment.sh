#!/usr/bin/env bash
# Full experiment, reproducible from a clean var/ directory. Version 3 (current code) adds the router, online memory and
# two new task families; version 2 re-validates verified programs from experience before asking a model; version 1 used
# text experience only and is kept for reference.
#   1. rebuild the frozen task packages (hashes must match tasks/lock.json)
#   2. learn on A serially from v0, two rounds; each run publishes a new snapshot
#   3. B: development comparison, v0 vs the learned snapshot, 3 repeats
#   4. D: sealed held-out comparison with the same frozen configuration, run once
#   5. S: sealed online stream from the learned snapshot (memory vs fresh, 3 replays of the learning), run once
#   6. router ablation on the T tasks (router on vs off, from the learned snapshot)
# Note: the recorded B and D comparisons ran under version 2; re-running them with this code uses version 3's prompt
# and router, so their fingerprints differ from the recorded ones.
# Usage: scripts/experiment.sh [learn|compare-b|compare-d|stream|ablation|all]
# Version 1 used: learn --label "formal A learning", then the B and C comparisons labelled "B dev comparison" and
# "C final held-out" (see docs/archive/memory-learning-results.md section 4).
set -euo pipefail
cd "$(dirname "$0")/.."

step=${1:-all}
learned() { uv run python -c "from quotacrux import db; print(db.one(\"SELECT snapshot_id FROM snapshots ORDER BY version DESC LIMIT 1\")['snapshot_id'])"; }
# The snapshot the S stream started from (online runs publish more versions, so "latest" no longer means "learned on A").
stream_start() { uv run python -c "from quotacrux import db; r = db.one(\"SELECT json_extract(plan_json, '$.start_snapshot') AS s FROM comparisons WHERE label LIKE 'S online stream%' ORDER BY created_at DESC LIMIT 1\"); print(r['s'] if r else '')"; }

if [[ $step == all || $step == learn ]]; then
  uv run quotacrux tasks build
  uv run quotacrux snapshots activate v0 --reason "learn from empty experience"
  uv run quotacrux learn A-01 A-02 A-03 A-04 A-05 A-06 --label "reuse A learning r1"
  uv run quotacrux learn A-01 A-02 A-03 A-04 A-05 A-06 --label "reuse A learning r2"
fi
if [[ $step == all || $step == compare-b ]]; then
  uv run quotacrux compare B-01 B-02 B-03 B-04 B-05 B-06 --a v0 --b "$(learned)" --repeats 3 --label "B dev comparison · reuse"
fi
if [[ $step == all || $step == compare-d ]]; then
  uv run quotacrux compare D-01 D-02 D-03 D-04 D-05 D-06 --a v0 --b "$(learned)" --repeats 3 --label "D final held-out · reuse"
fi
if [[ $step == all || $step == stream ]]; then
  start=$(learned)
  uv run quotacrux stream S-01 S-02 S-03 S-04 S-05 S-06 S-07 S-08 S-09 S-10 S-11 S-12 --start "$start" --repeats 3 \
    --label "S online stream · router"
fi
if [[ $step == all || $step == ablation ]]; then
  base=$(stream_start)
  scripts/router_ablation.sh 3 "${base:-$(learned)}"
fi
