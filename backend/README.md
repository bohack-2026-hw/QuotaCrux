# RouteEvo backend

M1 of the [shared core](../docs/shared-core-prd.md): one task family, the Qwen → GPT execution loop, a Docker
sandbox with an external evaluator, a resource ledger and a reproducible entry point. Decisions follow
[implementation-decisions.md](../docs/implementation-decisions.md).

## Setup

```sh
cd backend
uv sync                      # Python 3.12 + deps
cp .env.example .env         # fill OPENAI_API_KEY, QWEN_BASE_URL, QWEN_MODEL
uv run routeevo tasks build  # generate task packages from tasks/spec.json into var/tasks
```

Docker (OrbStack) must be running; the sandbox image is built on first use.

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
| `uv run routeevo serve` | HTTP API on :8000 for the frontend |
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
- After the loop the best candidate is frozen and tested once on the final data; that result never feeds back.

## Loop and budgets

Actions: `analyze`, `get_evidence` (cProfile), `propose_candidate` (validated immediately), `run_validation`,
`finish`. Defaults: 6 model requests, 4 candidates, 300 s loop, 120 s per request, 10 s per sample.
The small model runs first; after 2 consecutive candidates that are not correct-and-on-target the run switches to
the large model for good. Stop reasons: `goal_reached`, `budget_exhausted`, `agent_finished`, `user_stopped`,
`model_api_error`, `environment_error`, `internal_error`. Runs are globally serial (file lock).

Every model call stores provider, model, role, effort, tokens (`null` = unknown, never 0), latency, request id,
price-table version and estimated cost; raw requests and responses are in `var/runs/<id>/calls/`.

## API (polling, no streaming)

`GET /api/tasks`, `GET /api/tasks/{id}`, `GET|POST /api/runs`, `GET /api/runs/{id}` (report, also while running),
`GET /api/runs/{id}/events?after=N`, `POST /api/runs/{id}/stop`, `GET /api/runs/{id}/candidates/{cid}`,
`GET /api/snapshots`. Interactive docs at `/docs` when `routeevo serve` is running.
