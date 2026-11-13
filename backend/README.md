# RouteEvo backend

The [shared core](../docs/shared-core-prd.md), M1–M3: one task family, the Qwen → GPT execution loop, a Docker
sandbox with an external evaluator, a resource ledger, program-extracted experience with immutable snapshots and
rollback, frozen held-out comparisons, and an HTTP API that also serves the dashboard. Decisions follow
[implementation-decisions.md](../docs/implementation-decisions.md).

## Setup

```sh
cd backend
uv sync                      # Python 3.12 + deps
cp .env.example .env         # fill OPENAI_API_KEY, QWEN_BASE_URL, QWEN_MODEL
uv run routeevo tasks build  # regenerate the frozen task packages (hashes checked against tasks/lock.json)
(cd ../frontend && pnpm install && pnpm build)   # dashboard, served by `routeevo serve`
uv run routeevo serve        # http://127.0.0.1:8000
```

Docker (OrbStack) must be running; the sandbox image is built on first use. Local Qwen runs in Ollama
(`QWEN_MODEL=qwen3.8:27b-mlx`, thinking off via `QWEN_REASONING_EFFORT=none`). The project `.env` overrides the
shell, which matters because the shell may export `OPENAI_API_KEY=ollama` for local tools.

Full experiment from a clean `var/`: `scripts/experiment.sh` (learn on A, then compare B and C).

## Commands

| Command | Purpose |
| --- | --- |
| `uv run routeevo run A-01 [--mode learn\|eval] [--snapshot v0]` | One agent run with the real models; prints the summary and writes `var/runs/<id>/report.json` |
| `uv run routeevo run A-01 --script tests/fixtures/scripts/success.json` | Same loop with a scripted model; functional checks only, labelled in reports |
| `uv run routeevo report <run_id> [--json]` | Rebuild the report from stored records |
| `uv run routeevo runs` / `stop <run_id>` | List runs / request a stop after the current step |
| `uv run routeevo check A-01 path/to/candidate.py [--dataset final]` | Evaluate a program outside any run |
| `uv run routeevo calibrate A-01` | Time the initial program and fixed input-transfer overhead |
| `uv run routeevo tasks list` / `tasks lock` | Show tasks / pin manifests in `tasks/lock.json` before B/C comparisons |
| `uv run routeevo learn A-01 A-02 …` | Serial learn-mode runs; each publishes a snapshot on top of the previous one |
| `uv run routeevo snapshots list\|show v3\|diff v0 v3\|activate v1 --reason …` | Snapshots, diffs and rollback |
| `uv run routeevo experience <id>` | One experience record with its evidence |
| `uv run routeevo compare B-01 … --a v0 --b v6 --repeats 3` | Frozen held-out comparison (serial, alternating, no writes) |
| `uv run routeevo comparison <id> [--json]` | Comparison summary |
| `uv run routeevo explain <comparison_id>` / `export-run <run_id>` | Three-line evolution note / Markdown research record of one run |
| `uv run routeevo probe small\|large` | Send one real first-step request; prints latency, tokens, cost |
| `uv run routeevo serve` | HTTP API on :8000; also serves `frontend/dist` at `/` |
| `uv run pytest` | Unit tests plus end-to-end flows (needs Docker) |

## Task family `groupagg`

Group CSV rows `key,value` by key, output `key,count,sum` sorted by key ([contract](src/routeevo/families/groupagg.py)).
The initial program is a plain `csv` + dict implementation. A task package (`tasks/spec.json` → `var/tasks/<id>/`)
holds the contract, initial code, visible examples, a dev data profile, dev data and an independent final test set,
all hash-pinned in `manifest.json`. Only contract, initial code, examples and dev profile reach the model.

## Evaluation

- Every sample runs in a fresh container: no network, read-only root, non-root user, 1 CPU, 1 GB, 64 pids.
  Only the candidate file (read-only) and stdin input enter it; reference outputs stay on the host.
- Timing starts after the in-container harness reports ready and stops when the host has the full stdout, so
  container and interpreter startup are excluded (reported separately).
- Candidate check run, baseline check run, then 5 alternating rounds (order flipped each round).
  Speedup = baseline median / candidate median.
- **Improved** means every candidate sample beat every baseline sample (one-sided Mann-Whitney U = 0, p = 1/252).
  Only improved candidates can replace the best artifact; the goal is improved and speedup ≥ 1.10.
- Before timing, candidates must also pass small public contract cases (empty input, interleaved repeats, ASCII
  order, big integers, an almost-sorted trap, 32-char keys), so data-specific shortcuts without a fallback fail.
- After the loop the best candidate is frozen and tested once on the final data; that result never feeds back.

## Experience, snapshots, comparison

- Learn-mode runs (A and smoke tasks only) end by extracting one record per model candidate with a usable dev
  evaluation: workload conditions (profile + buckets), the change (code features, diff vs the initial program),
  the measured result, resources and source ids. Success, no-gain and failure are all kept. Model explanations are
  stored as unverified hypotheses. Records are published atomically as `v{n}` (parent = the snapshot the run read)
  and the active pointer moves to it; no qualifying records means no new version.
- Every run reads one snapshot fixed at start. Retrieval is deterministic: at least 3 of 5 workload buckets must
  match; up to 3 successes, 2 failures, 1 no-gain are injected with match details and sample counts. The run
  records exactly which experiences it read.
- Rollback switches the active pointer only (refused while a learn run is in progress); history stays.
- `compare` runs held-out tasks with two frozen snapshots, alternating order, serially, rejects tasks that
  contributed experience to either snapshot, checks that all runs share one config fingerprint, and reports
  per-side and per-task results plus the learning cost along the snapshot lineage.
- A two-round session (`POST /api/sessions`) learns one task from a base snapshot, publishes the new version (which
  becomes active), then runs a one-repeat comparison of base vs new on an unseen task. Re-activate the formal
  snapshot afterwards.

## Loop and budgets

Actions: `analyze`, `get_evidence` (cProfile), `propose_candidate` (validated immediately), `run_validation`,
`finish`. Defaults: 6 model requests, 4 candidates, 300 s loop, 120 s per request, 10 s per sample.
The small model runs first; after 2 consecutive candidates that are not correct-and-on-target, or 3 small-model
requests without an on-target candidate (`upgrade-rule-v2`; B ran under v1, which only had the first condition), the
run switches to the large model for good. `goal_reached` means the dev-data goal stopped the loop; the frozen best
candidate's final test is reported separately and can still miss. Stop reasons: `goal_reached`, `budget_exhausted`, `agent_finished`, `user_stopped`,
`model_api_error`, `environment_error`, `internal_error`. Runs are globally serial (file lock).

Every model call stores provider, model, role, effort, tokens (`null` = unknown, never 0), latency, request id,
price-table version and estimated cost; raw requests and responses are in `var/runs/<id>/calls/`.

## API (polling, no streaming)

`GET /api/tasks`, `GET /api/tasks/{id}`, `GET|POST /api/runs`, `GET /api/runs/{id}` (report, also while running),
`GET /api/runs/{id}/events?after=N`, `POST /api/runs/{id}/stop`, `GET /api/runs/{id}/candidates/{cid}`,
`GET /api/snapshots`, `GET /api/snapshots/{id}`, `GET /api/snapshots/{a}/diff/{b}`, `PUT /api/snapshots/active`,
`GET /api/experiences/{id}`, `GET|POST /api/comparisons`, `GET /api/comparisons/{id}`,
`POST /api/comparisons/{id}/stop`, `GET /api/comparisons/{id}/note` (three-line evolution note),
`GET|POST /api/sessions`, `GET /api/runs/{id}/markdown` (research record). Interactive docs at `/docs` when `routeevo serve` is running.
