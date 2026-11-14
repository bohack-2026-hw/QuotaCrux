"""ALE-Bench batch tasks with the released AtCoder generator and score calculator."""
from __future__ import annotations

import json
import shutil
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from .. import config, db, taskpkg
from ..sandbox import executor
from . import native
from .native import MIN_MATCHES, buckets, compatible

DATA_REVISION = "0f426173b4e4e73b09b2b3631ae0490f66b75f99"
SUPPORTED = ("ahc024", "ahc026")
BASE_IMAGE = "python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
INITIAL = {
    "ahc024": "import sys\nlines = sys.stdin.read().splitlines()\nprint('\\n'.join(lines[1:]))\n",
    "ahc026": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
for value in range(1, n + 1):
    src = next(i for i, stack in enumerate(stacks) if value in stack)
    position = stacks[src].index(value)
    if position + 1 < len(stacks[src]):
        dest = min((j for j in range(m) if j != src), key=lambda j: len(stacks[j]))
        above = stacks[src][position + 1:]
        print(above[0], dest + 1)
        stacks[dest].extend(above)
        del stacks[src][position + 1:]
    print(value, 0)
    stacks[src].pop()
''',
}


def prepare(problem: str) -> tuple[dict, dict, Path]:
    if problem not in SUPPORTED:
        raise ValueError(f"supported ALE-Bench batch tasks: {SUPPORTED}")
    cache = config.VAR_DIR / "benchmarks" / "ale" / DATA_REVISION / problem
    archive = native.fetch(f"https://huggingface.co/datasets/SakanaAI/ALE-Bench/resolve/{DATA_REVISION}/{problem}.zip", cache / "task.zip")
    context = cache / "image"
    context.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        entries = {str(PurePosixPath(n)): n for n in z.namelist() if not n.endswith("/")}
        metadata = json.loads(z.read(entries[f"{problem}/data.json"]))
        if metadata["metadata"]["problem_type"] != "batch" or metadata["metadata"]["score_type"] != "maximize":
            raise ValueError("only batch tasks with maximization scores are supported")
        for path, name in entries.items():
            p = PurePosixPath(path)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("unsafe path in ALE archive")
            if path.startswith(f"{problem}/tools/") and (path.endswith(".rs") or p.name in ("Cargo.toml", "Cargo.lock")):
                dest = context / p.relative_to(problem)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(name))
        statement = z.read(entries[f"{problem}/statement_en.md"]).decode()
    shutil.copyfile(native.TOOLS / "ale_worker.py", context / "ale_worker.py")
    (context / "Dockerfile").write_text(f'''FROM {BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends cargo rustc ca-certificates && rm -rf /var/lib/apt/lists/*
COPY tools /build/tools
WORKDIR /build/tools
RUN cargo build --release --locked --bin gen --bin vis && mkdir -p /opt/ale && cp target/release/gen target/release/vis /opt/ale/
COPY ale_worker.py /opt/ale/worker.py
USER 65534:65534
WORKDIR /tmp
''')
    env = native.build_image(context, f"ale-{problem}")
    return {**metadata, "statement": statement}, env, archive


def import_problem(problem: str, *, split: str, dev_cases: int = 5, final_cases: int = 150,
                   task_id: str | None = None) -> taskpkg.Task:
    if dev_cases < 1 or final_cases < 1:
        raise ValueError("case counts must be positive")
    metadata, env, archive = prepare(problem)
    seeds = metadata["seeds"]
    if dev_cases > len(seeds["public"]) or final_cases > len(seeds["private"]):
        raise ValueError("requested case count exceeds released public/private split")
    selected = {"dev": seeds["public"][:dev_cases], "final": seeds["private"][:final_cases]}
    if set(selected["dev"]) & set(selected["final"]):
        raise ValueError("ALE public/private seed overlap")
    suites = {}
    for name, chosen in selected.items():
        inputs = native.worker(env["image_id"], "/opt/ale/worker.py", {"operation": "generate", "seeds": chosen})["inputs"]
        if len(inputs) != len(chosen):
            raise RuntimeError("ALE generator returned an unexpected number of cases")
        suites[name] = [{"id": f"{name}-{i}", "seed": seed, "input": text} for i, (seed, text) in enumerate(zip(chosen, inputs))]
    constraints = metadata["constraints"]
    source = {"dataset": "SakanaAI/ALE-Bench", "revision": DATA_REVISION,
              "archive_sha256": taskpkg.sha256_file(archive), "license": "CC-BY-ND-4.0"}
    contract = (metadata["statement"] + "\n\nQuotaCrux protocol: Python 3.12 stdin/stdout. "
                "Maximize the sum of raw AtCoder scores while passing every case. "
                "The initial program is a simple feasible starter, not an official competitive baseline. "
                "Do not interpret score differences as runtime speedups. The private suite is hidden.\n")
    return native.package("ale-bench", problem, split, source, contract, INITIAL[problem], suites["dev"], suites["final"],
        objective={"metric": "score", "direction": "maximize"}, settings={**env, "time_limit_s": constraints["time_limit"],
            "memory_limit_bytes": constraints["memory_limit"], "allowed_imports": [], "candidate_interface": "stdin_stdout"}, task_id=task_id)


def presentation(manifest: dict) -> dict:
    return {"title": f"ALE-Bench · {manifest['problem']['key']}",
        "workload": f"{manifest['problem']['key']} · {manifest['dev_params']['cases']} public cases",
        "baseline": "可行起始程序（不代表上游竞争性解法）", "validation": "AtCoder 原始裁判；全部用例合法，最大化原始得分之和",
        "agent_notes": "Score optimization, not runtime optimization. Keep every output valid and maximize total score. "
                       "Use a complete Python standard-library stdin/stdout program. No profile tool is available; "
                       "propose_candidate and run_validation return per-case scores."}


def environment_info(task, measure) -> dict:
    env = executor.environment_info(measure)
    env["judge"] = {k: task.manifest["native"][k] for k in ("image_tag", "image_id")}
    return env


def evaluate(task, code, dataset, measure, limits, *, run_id=None, candidate_id=None, measure_timing=True,
             baseline_code=None, deadline=None):
    from ..evaluator import Evaluation
    started, t0 = db.now(), time.perf_counter()
    ev = Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "pending", False, None, None, None, None, None, None, None)
    records = native.cases(task, dataset)
    samples, outputs = [], []
    settings = task.manifest["native"]
    try:
        for case in records:
            timeout = native.remaining_timeout(deadline, min(limits.measurement_timeout_s, settings["time_limit_s"]))
            if timeout <= 0:
                ev.status = "budget_exhausted"
                return ev
            sample = executor.run_sample(code, case["input"].encode(), timeout, measure)
            samples.append({"case": case["id"], **sample.summary()})
            if sample.status != "ok":
                ev.status = sample.status
                ev.correct = False
                ev.detail["failure"] = {"category": sample.status, "case": case["id"], "stderr_tail": sample.stderr_tail}
                return ev
            outputs.append({"input": case["input"], "output": sample.stdout.decode("utf-8")})
        ev.executed = True
        timeout = native.remaining_timeout(deadline, 10 * len(records))
        if timeout <= 0:
            ev.status = "budget_exhausted"
            return ev
        result = native.worker(settings["image_id"], "/opt/ale/worker.py", {"operation": "judge", "cases": outputs}, timeout=timeout)
        scores = result["cases"]
        if len(scores) != len(records) or any(not native.finite_number(x["score"]) for x in scores):
            raise ValueError("invalid ALE score result")
        ev.correct = ev.format_ok = all(x["correct"] for x in scores)
        ev.status = "passed" if ev.correct else "wrong_output"
        value = sum(x["score"] for x in scores)
        baseline = None
        if run_id:
            row = db.one("SELECT detail_json FROM evaluations WHERE run_id=? AND candidate_id='c0' AND dataset=? ORDER BY started_at LIMIT 1", (run_id, dataset))
            if row:
                baseline = json.loads(row["detail_json"])["objective"]["value"]
        if code == task.initial_code.encode():
            baseline = value
        elif baseline is None and ev.correct:
            reference = evaluate(task, task.initial_code.encode(), dataset, measure, limits,
                                 run_id=run_id, candidate_id="c0" if run_id else None,
                                 measure_timing=False, deadline=deadline)
            if reference.status != "passed":
                raise RuntimeError(f"initial program failed {dataset} scoring: {reference.status}")
            baseline = reference.detail["objective"]["value"]
        ev.detail["objective"] = {"metric": "score", "direction": "maximize", "value": value,
                                   "baseline": baseline, "aggregation": "sum", "cases": scores}
        ev.detail["case_count"] = len(records)
        ev.detail["passed_cases"] = sum(x["correct"] for x in scores)
        ev.improved = bool(ev.correct and baseline is not None and value > baseline)
        ev.goal_met = ev.improved
        if not ev.correct:
            ev.detail["failure"] = {"category": "wrong_output", "message": "one or more outputs violate task constraints"}
        return ev
    except (RuntimeError, ValueError, KeyError, UnicodeError) as exc:
        ev.status = "budget_exhausted" if deadline is not None and time.perf_counter() >= deadline else "checker_error"
        ev.detail["failure"] = {"category": "checker_error", "message": str(exc)}
        return ev
    finally:
        ev.detail["samples"] = samples
        ev.detail["container_ready_latency_s"] = sum(s.get("ready_latency_s") or 0 for s in samples)
        native.persist(task, ev, code, started, t0, run_id, candidate_id)
