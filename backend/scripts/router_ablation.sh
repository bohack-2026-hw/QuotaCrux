#!/usr/bin/env bash
# Router ablation on new task families: the same tasks from v19 (which holds no logstats/intervals experience), router
# on (straight to the large model) vs router off (local small model first, upgrade rule as before). Eval mode, nothing is
# written. The two arms differ in exactly one configuration key (router), so their fingerprints differ by design.
# Order alternates per task and repeat. Usage: scripts/router_ablation.sh [repeats] [snapshot]
set -euo pipefail
cd "$(dirname "$0")/.."
repeats=${1:-3}
snap=${2:-v19}
i=0
for rep in $(seq 1 "$repeats"); do
  for t in T-L1 T-L2 T-I1 T-I2; do
    if (( (rep + i) % 2 == 0 )); then order="on off"; else order="off on"; fi
    for arm in $order; do
      if [[ $arm == on ]]; then
        uv run routeevo run "$t" --mode eval --snapshot "$snap" --label "router ablation · on" | sed -n 's/^\(run\|status\|cost\|time\) */\1 /p'
      else
        uv run routeevo run "$t" --mode eval --snapshot "$snap" --no-router --label "router ablation · off" | sed -n 's/^\(run\|status\|cost\|time\) */\1 /p'
      fi
    done
    i=$((i + 1))
  done
done
