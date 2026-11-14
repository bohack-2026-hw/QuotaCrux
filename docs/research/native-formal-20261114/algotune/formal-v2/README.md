# Mac AlgoTune formal timing-v2 candidate

This directory is the isolated timing-v2 candidate for issue #4. The parent
`algotune/` evidence remains the timing-v1 provisional preflight and is not
rewritten or presented as an accepted formal calibration.

The frozen runtime source is `912b20a4cfeb51af9c36d0679b23f0990abe862f`.
The committed executor may be a documentation-only descendant, but its
preflight rejects any runtime or calibration-script difference from that SHA.

No hosted model request or held-out final evaluation has been made for this
candidate. `freeze-candidate.json` intentionally remains blocked until:

1. the central plan binds the rebuilt Mac task and image identities;
2. both tasks pass a quiet-window 3-warmup/5-timing calibration; and
3. the calibration artifact and SHA256 are bound into the freeze manifest.

The task packages are registered in the dedicated absolute VAR directory
`backend/var-algotune-formal-912b20a-20261114`. They use native arm64 images and
`isolated-function-timing-v2`, which disables automatic cyclic GC only during
the timed `solve(problem)` call and restores it in `finally`.

## Read-only preflight

Run from the repository root. Both `--root` and `--out` must be absolute so
Docker mounts and evidence locations cannot depend on the caller's directory.

```bash
export ROUTEEVO_VAR_DIR="$PWD/backend/var-algotune-formal-912b20a-20261114"
uv run --project backend python \
  docs/research/native-formal-20261114/algotune/formal-v2/run_algotune.py \
  --root "$ROUTEEVO_VAR_DIR" \
  --manifest "$PWD/docs/research/native-formal-20261114/algotune/formal-v2/freeze-candidate.json" \
  --out "$PWD/backend/var-algotune-formal-912b20a-20261114/formal-output"
```

The preflight does not call the model or execute final inputs. It reports
missing hosted settings by variable name only and never prints their values.
Formal execution additionally requires `--execute`; the runner refuses that
flag while the manifest or calibration is blocked.

## Execution semantics

The 15 Mac entries preserve the preregistered interleaved local order as seq
1-15 and bind each entry separately to central slots 16-30. They run with
concurrency 1. Each slot is persisted independently, so an ordinary final
failure remains recorded and later slots continue. Infrastructure, model API,
internal, or explicit stop errors interrupt the batch. `--resume --execute`
only opens slots without evidence and never silently replaces a recorded slot.

The runner verifies the frozen runtime source, its own bytes, central plan,
task and SQLite manifests, container image IDs, timing protocol and GC policy,
prompt/schema hashes, hosted model public configuration, price snapshot,
Docker VM resources, calibration evidence, and start-of-run host load before
any model action.
