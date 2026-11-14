# QuotaCrux（枢决） backend

The project is named **QuotaCrux（枢决）**. The Python package and CLI are `quotacrux`; use `QUOTACRUX_VAR_DIR` and `QUOTACRUX_NO_DOTENV` for configuration. Existing `ROUTEEVO_VAR_DIR` / `ROUTEEVO_NO_DOTENV` values and `routeevo.sqlite3` databases remain supported. New stores use `quotacrux.sqlite3`.

The [shared core](../docs/requirements/core-requirements.md), M1–M3: three task families, the Qwen / GPT execution loop with a router,
a Docker sandbox with an external evaluator, a resource ledger, program-extracted experience with immutable snapshots
and rollback, frozen held-out comparisons, an online stream comparison, and an HTTP API that also serves the
dashboard. Boundary conditions, case by case: [docs/archive/legacy-runtime-rules.md](../docs/archive/legacy-runtime-rules.md). Decisions follow
[initial implementation decisions](../docs/archive/initial-implementation-decisions.md).

## Setup

```sh
cd backend
uv sync                      # Python 3.12 + deps
cp .env.example .env         # fill OPENAI_API_KEY, QWEN_BASE_URL, QWEN_MODEL
uv run quotacrux tasks build  # regenerate the frozen task packages (hashes checked against tasks/lock.json)
(cd ../frontend && pnpm install && pnpm build)   # dashboard, served by `quotacrux serve`
uv run quotacrux serve        # http://127.0.0.1:8000
```

Docker (OrbStack) must be running; the sandbox image is built on first use. Local Qwen runs in Ollama
(`QWEN_MODEL=qwen3.8:27b-mlx`, thinking off via `QWEN_REASONING_EFFORT=none`). The project `.env` overrides the
shell, which matters because the shell may export `OPENAI_API_KEY=ollama` for local tools.

Full experiment from a clean `var/`: `scripts/experiment.sh` (learn on A, compare B and D, the S stream, the router
ablation).

## Commands

| Command | Purpose |
| --- | --- |
| `uv run quotacrux run A-01 [--mode eval\|online\|learn] [--snapshot v0] [--no-router]` | One agent run with the real models; prints the summary and writes `var/runs/<id>/report.json` |
| `uv run quotacrux run A-01 --script tests/fixtures/scripts/success.json` | Same loop with a scripted model; functional checks only, labelled in reports |
| `uv run quotacrux report <run_id> [--json]` | Rebuild the report from stored records |
| `uv run quotacrux runs` / `stop <run_id>` | List runs / request a stop after the current step |
| `uv run quotacrux check A-01 path/to/candidate.py [--dataset final]` | Evaluate a program outside any run |
| `uv run quotacrux calibrate A-01` | Time the initial program and fixed input-transfer overhead |
| `uv run quotacrux tasks list` / `tasks lock` | Show tasks / pin manifests in `tasks/lock.json` before B/C comparisons |
| `uv run quotacrux learn A-01 A-02 …` | Serial learn-mode runs; each publishes a snapshot on top of the previous one |
| `scripts/experiment.sh [learn\|compare-b\|compare-d\|stream\|ablation]` | The formal experiment: two A learning rounds from v0, B comparison, sealed D comparison, sealed S stream, router ablation |
| `uv run quotacrux stream S-01 … --start v19 --repeats 3` | Online stream: the same task sequence with accumulating memory (online mode) vs from a fixed start (eval), alternating, serial |
| `uv run quotacrux snapshots list\|show v3\|diff v0 v3\|activate v1 --reason …` | Snapshots, diffs and rollback |
| `uv run quotacrux experience <id>` | One experience record with its evidence |
| `uv run quotacrux compare B-01 … --a v0 --b v6 --repeats 3` | Frozen held-out comparison (serial, alternating, no writes) |
| `uv run quotacrux comparison <id> [--json]` | Comparison summary |
| `uv run quotacrux ablate-routing B-01 … --snapshot v0 --repeats 3` | Four independent action/model routing combinations on one frozen snapshot; [protocol](../docs/design/action-model-routing.md) |
| `uv run quotacrux explain <comparison_id>` / `export-run <run_id>` | Note on what experience changed / Markdown research record of one run |
| `uv run quotacrux export-run <run_id> --bundle DIR` | Research deliverable: record, `best.py`, all candidates, raw model calls, `report.json`, `reproduce.sh` |
| `uv run quotacrux probe small\|large` | Send one real first-step request; prints latency, tokens, cost |
| `uv run quotacrux serve` | HTTP API on :8000; also serves `frontend/dist` at `/` |
| `uv run pytest` | Unit tests plus end-to-end flows (needs Docker) |

## Task families

| Family | Task | Initial program |
| --- | --- | --- |
| `groupagg` | group CSV rows `key,value`, output `key,count,sum` sorted by key | `csv` + dicts + `sorted` |
| `logstats` | access log lines → per (hour, method, path): count, 5xx count, latency sum and max | regex + `datetime.strptime` |
| `intervals` | merge overlapping or touching closed integer intervals (values up to ±10^12) | `csv` + tuple sort |

Each family is one module in `src/quotacrux/families/`: contract, initial program, deterministic generator, trusted
reference output, workload profile and 5 condition buckets, 7 public contract cases, output checker. The evaluator,
experience store, router and UI dispatch on the task's family. A task package (`tasks/spec*.json` →
`var/tasks/<id>/`) holds the contract, initial code, visible examples, a dev data profile, dev data and an independent
final test set, all hash-pinned in `manifest.json`. Only contract, initial code, examples and dev profile reach the
model. Splits: A (learning), B (development comparison), C (held-out for the text-experience version), D (sealed
before re-use was built), T (tuning tasks for the new families), S (sealed mixed-family stream, run once for version
3), smoke (tests). Writable splits: A, S, T, smoke.

## Evaluation

- Every sample runs in a fresh container: no network, read-only root, non-root user, 1 CPU, 1 GB, 64 pids.
  Only the candidate file (read-only) and stdin input enter it; reference outputs stay on the host.
- Timing starts after the in-container harness reports ready and stops when the host has the full stdout, so
  container and interpreter startup are excluded (reported separately).
- Candidate check run, baseline check run, then 5 alternating rounds (order flipped each round).
  Speedup = baseline median / candidate median.
- **Improved** means every candidate sample beat every baseline sample (one-sided Mann-Whitney U = 0, p = 1/252).
  Only improved candidates can replace the best artifact; the goal is improved and speedup ≥ 1.10.
- Before timing, candidates must also pass the family's 7 public contract cases (groupagg: empty input,
  interleaved repeats, ASCII order, big integers, an almost-sorted trap, 32-char keys; logstats: hour and day
  boundaries, out-of-order lines, status 499/500/599; intervals: touching vs gap of one, transitive merges, ±10^12),
  so data-specific shortcuts without a fallback fail.
- After the loop the best candidate is frozen and tested once on the final data; that result never feeds back.

## Experience, snapshots, comparison

- Learn- and online-mode runs (writable splits only) end by extracting one record per model or re-validated candidate with a
  usable dev evaluation: workload conditions (profile + buckets), the change (the full program, code features, diff
  vs the initial program), the measured result, resources and source ids (`extractor-v3`). Success, no-gain and failure are all kept. Model explanations are
  stored as unverified hypotheses. Records are published atomically as `v{n}` (parent = the snapshot the run read)
  and the active pointer moves to it; no qualifying records means no new version.
- Every run reads one snapshot fixed at start. Retrieval is deterministic and family-scoped (`retrieval-v2`): at
  least 3 of the family's 5 workload buckets must match; up to 3 successes, 2 failures, 1 no-gain are injected with match details and sample counts. The run
  records exactly which experiences it read.
- Re-use (`reuse-v1`, `memory.REUSE`): before the first model request a run re-validates up to 3 verified programs
  from its snapshot with the normal dev evaluation — programs from success records, ranked by how many workload
  buckets their best success matches, then by measured speedup; equal programs (ignoring blank lines and trailing
  spaces) count once; a program is skipped when a no-gain or failure record matches the workload more closely than
  any of its successes. An eval run that reaches the target this way stops without calling a model (stop detail
  `re-used cN …; no model request needed`). A learn run instead raises its own target to 5% above the best re-used
  program (`set_target` step) so its model requests go to beating it. Each re-use is an experiment with a
  program-written hypothesis (source, recorded speedup, differing buckets) and a program verdict.
- Router (`router-v1`, `memory.ROUTER`): when re-use did not reach the target, the run starts on the small model if
  the snapshot holds a success of the same family matching at least 3 of 5 buckets (`familiar`); otherwise it goes
  straight to the large model — `new_family` (no record of the family) or `new_conditions` (records, but no similar
  success). The decision is a `route_model` program step with its reason. `--no-router` always starts small (ablation;
  changes the fingerprint).
- Modes: `eval` reads a frozen snapshot and writes nothing; `online` delivers like eval (stops when re-use reaches the
  target) and then publishes what it verified; `learn` raises the target above re-used programs and publishes.
- Rollback switches the active pointer only (refused while a learn or online run is in progress); history stays.
- `compare` runs held-out tasks with two frozen snapshots, alternating order, serially, rejects tasks that
  contributed experience to either snapshot, checks that all runs share one config fingerprint, and reports
  per-side and per-task results plus the learning cost along the snapshot lineage.
- `stream` runs a task sequence twice per repeat: arm `memory` in online mode, each task reading what the previous
  task of the same repeat published; arm `fresh` in eval mode on the start snapshot. Arms alternate per task; each
  repeat replays the learning from the start snapshot; the active pointer is restored afterwards. The summary
  reports both arms, first-of-family vs later tasks, per family, per position, cumulative large-model cost and
  snapshot growth.
- A two-round session (`POST /api/sessions`) learns one task from a base snapshot, publishes the new version (which
  becomes active), then runs a one-repeat comparison of base vs new on an unseen task. Re-activate the formal
  snapshot afterwards.

## Research view

Every report carries `research`: the task definition fixed before the run (question, workload, baseline, allowed
scope, tools, verification method, budget, final-test rule) and one experiment per proposed candidate with the
model's purpose, hypothesis, expected result and verification method (for re-used programs, written by the program),
the measured result, and a verdict assigned by the program against the target in force at the time — `supported` (improved and on target), `partial` (improved, below target), `refuted` (correct, no
improvement), `untestable` (the candidate failed), `untested`. `scripts/write_results.py` aggregates verdicts over all
formal runs; `scripts/export_research.py` exports rule-selected sample bundles to `docs/research/`.

## Loop and budgets

Actions: `analyze`, `get_evidence` (cProfile), `propose_candidate` (validated immediately), `run_validation`,
`finish`. Defaults: 6 model requests, 4 candidates, 300 s loop, 120 s per request, 10 s per sample.
`run` and `learn` accept `--action-router llm|decisions|jev` and `--model-router rule|decisions|jev` (defaults: `llm`, `rule`).
Both decision providers share the request/token/time budget with generation; reports split routing and generation usage.
See [routing adapters](../docs/design/action-model-routing.md) for the execution flow, API fields and four-way ablation.

OpenAI Decisions and TypeSafe Jev routing support non-native `legacy` runs and explicit
`--research-mode feedback --research-model-policy adaptive` research, including native tasks.
Fixed research and independent runs require the default `llm` + `rule` combination.
`--fixed-model small|large` fixes the generation role and skips model-router requests and upgrades.
Initial routing from experience is separate: `--no-router` starts on the small model unless a model is fixed;
`--model-router decisions|jev` also disables initial memory routing so the selected provider can make the model choice.
`ablate-routing` retains its existing four OpenAI Decisions combinations with initial memory routing disabled and one frozen snapshot.

For Jev, set `TYPESAFE_API_KEY` in the ignored `backend/.env`. `TYPESAFE_MODEL` defaults to the pinned
`jev-1.14.0`; responses record the actual model version, choice, confidence, full distribution, tokens and latency.
The adapter uses the existing `httpx` dependency and makes one HTTP attempt per budgeted call. For example:

```sh
uv run quotacrux run B-01 --snapshot v0 --no-router --action-router jev --model-router rule
uv run quotacrux run B-01 --snapshot v0 --action-router jev --model-router jev
```

The HTTP `POST /api/runs` fields `action_router` and `model_router` also accept `jev`.

For legacy runs with rule-based model selection, the initial router picks the starting model. A run that starts small
switches after 2 consecutive candidates that are not correct-and-on-target, or 3 small-model requests without an
on-target candidate (`upgrade-rule-v2`; B ran under v1, which only had the first condition). The switch to the large
model is irreversible. Legacy `goal_reached` means the dev-data goal stopped the loop; the frozen best
candidate's final test is reported separately and can still miss. Stop reasons: `goal_reached`, `budget_exhausted`, `agent_finished`, `user_stopped`,
`model_api_error`, `environment_error`, `internal_error`. Runs are globally serial (file lock).

Every model call stores provider, model, role, effort, tokens (`null` = unknown, never 0), latency, request id,
price-table version and estimated cost; raw requests and responses are in `var/runs/<id>/calls/`.

## API (polling, no streaming)

`GET /api/tasks`, `GET /api/tasks/{id}`, `GET|POST /api/runs`, `GET /api/runs/{id}` (report, also while running),
`GET /api/runs/{id}/events?after=N`, `POST /api/runs/{id}/stop`, `GET /api/runs/{id}/candidates/{cid}`,
`GET /api/snapshots`, `GET /api/snapshots/{id}`, `GET /api/snapshots/{a}/diff/{b}`, `PUT /api/snapshots/active`,
`GET /api/experiences/{id}`, `GET|POST /api/comparisons`, `POST /api/streams`, `GET /api/comparisons/{id}` (streams too),
`POST /api/comparisons/{id}/stop`, `GET /api/comparisons/{id}/note` (three-line evolution note),
`GET|POST /api/sessions`, `GET /api/runs/{id}/markdown` (research record). Interactive docs at `/docs` when `quotacrux serve` is running.

## Additional benchmark: EffiBench-X

`uv sync --extra benchmark --python 3.12.11` enables the pinned Python dataset importer.
For example, `uv run quotacrux tasks import-effibench codeforces/2104A --split smoke --dev-cases 3 --case-limit 6`
imports a small trial task; use `--parquet PATH` for a local, checksum-verified shard.
See [adapter boundaries, dataset size and evaluation protocol](../docs/design/effibench-integration.md)
and [pilot validation](../docs/archive/effibench-preflight.md). Run `uv run --extra benchmark pytest` to include importer tests.

ALE-Bench, AlgoTune and KernelBench research subsets are available through `tasks import-ale-bench`,
`tasks import-algotune` and `tasks import-kernelbench`. `research-compare` runs equal-budget feedback versus
independent attempts within a task, using an empty snapshot and one fixed model.
See [supported tasks, native evaluators and GPU worker setup](../docs/design/native-benchmarks.md).
