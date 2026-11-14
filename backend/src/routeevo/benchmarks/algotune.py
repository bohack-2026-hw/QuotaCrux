"""AlgoTune CPU subset: frozen upstream generators/checkers and isolated function timing."""
from __future__ import annotations

import ast
import json
import shutil
import statistics
import time
import uuid

from .. import config, db, taskpkg
from ..sandbox import executor
from . import native
from .ale import BASE_IMAGE
from .native import MIN_MATCHES, buckets, compatible

SOURCE_REVISION = "dff9914c10800c7a031c9e8c3d4d1c8cd1b38906"
SUPPORTED = ("convolve_1d", "pagerank")


def scientific_image() -> dict:
    context = config.VAR_DIR / "benchmarks" / "algotune" / "candidate-image"
    context.mkdir(parents=True, exist_ok=True)
    for name in ("wire.py", "scientific_harness.py"):
        shutil.copyfile(native.TOOLS / name, context / name)
    (context / "Dockerfile").write_text(f'''FROM {BASE_IMAGE}
USER root
RUN pip install --no-cache-dir numpy==2.5.4 scipy==1.18.1 networkx==3.7
COPY wire.py scientific_harness.py /opt/routeevo/
USER 65534:65534
WORKDIR /work
''')
    return native.build_image(context, "scientific")


def reference_program(source: str) -> str:
    tree = ast.parse(source)
    body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "AlgoTuneTasks.base":
            continue
        if isinstance(node, ast.ClassDef):
            node.bases = [ast.Name(id="object", ctx=ast.Load())]
            node.decorator_list = []
            node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in ("__init__", "solve")]
            class_name = node.name
        body.append(node)
    tree.body = body
    return ("# Solver extracted from AlgoTune " + SOURCE_REVISION + "; see UPSTREAM_LICENSE.txt.\n"
            "# Copyright (c) 2025 Ori Press and the AlgoTune contributors\n" +
            ast.unparse(ast.fix_missing_locations(tree)) + f"\n\ndef solve(problem):\n    return {class_name}().solve(problem)\n")


def import_problem(problem: str, *, split: str, size: int = 1000, dev_cases: int = 5,
                   final_cases: int = 15, seed: int = 1729, task_id: str | None = None) -> taskpkg.Task:
    if problem not in SUPPORTED:
        raise ValueError(f"supported AlgoTune tasks: {SUPPORTED}")
    if min(size, dev_cases, final_cases) < 1 or not 0 <= seed < 2**32 - dev_cases - final_cases:
        raise ValueError("invalid size, case counts or seed")
    cache = config.VAR_DIR / "benchmarks" / "algotune" / SOURCE_REVISION / problem
    path = native.fetch(f"https://raw.githubusercontent.com/oripress/AlgoTune/{SOURCE_REVISION}/AlgoTuneTasks/{problem}/{problem}.py", cache / "task.py")
    license_path = native.fetch(f"https://raw.githubusercontent.com/oripress/AlgoTune/{SOURCE_REVISION}/LICENSE", cache / "LICENSE")
    candidate_env = scientific_image()
    context = cache / "judge-image"
    context.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, context / "task.py")
    shutil.copyfile(native.TOOLS / "algotune_worker.py", context / "worker.py")
    (context / "Dockerfile").write_text(f"FROM {candidate_env['image_tag']}\nCOPY task.py /opt/algotune/task.py\nCOPY worker.py /opt/routeevo/algotune_worker.py\n")
    judge_env = native.build_image(context, f"algotune-{problem}")
    seeds = list(range(seed, seed + dev_cases + final_cases))
    generated = native.worker(judge_env["image_id"], "/opt/routeevo/algotune_worker.py",
        {"operation": "generate", "seeds": seeds, "size": size}, timeout=300)["problems"]
    if len(generated) != len(seeds):
        raise RuntimeError("unexpected AlgoTune generator case count")
    records = [{"id": str(i), "problem": value} for i, value in enumerate(generated)]
    source = {"repository": "oripress/AlgoTune", "revision": SOURCE_REVISION, "task_sha256": taskpkg.sha256_file(path), "license": "MIT"}
    contract = (f"Optimize AlgoTune {problem}. Submit a Python module exposing solve(problem). "
                "NumPy, SciPy and NetworkX are available. The initial code defines the exact input and output interface. "
                "Every result must pass the pinned upstream numerical checker; NaN/Inf and incorrect shapes are rejected. "
                "Do not read stdin or write stdout. Timing covers the solve call, excluding imports and serialization. "
                "Every measurement uses fresh candidate globals and a fresh input object.\n")
    return native.package("algotune", problem, split, source, contract, reference_program(path.read_text()),
        records[:dev_cases], records[dev_cases:], objective={"metric": "speedup", "direction": "maximize"},
        settings={"candidate_image": candidate_env, "judge_image": judge_env, "size": size, "seed": seed,
            "allowed_imports": ["numpy", "scipy", "networkx"], "candidate_interface": "solve"}, task_id=task_id,
        extra_files={"upstream_task.py": path.read_bytes(), "UPSTREAM_LICENSE.txt": license_path.read_bytes()})


def presentation(manifest: dict) -> dict:
    return {"title": f"AlgoTune · {manifest['problem']['key']}",
        "workload": f"{manifest['problem']['key']} · n={manifest['native']['size']} · {manifest['dev_params']['cases']} dev cases",
        "baseline": "上游 solve 方法；独立函数计时", "validation": "上游数值校验器 + 形状及有限数值检查；每次计时结果均校验",
        "agent_notes": "Submit a Python module with solve(problem), not a stdin/stdout program. "
                       "NumPy/SciPy/NetworkX are installed. Function timing excludes import/serialization. "
                       "No cProfile tool is available; use measured validation feedback. Cross-run caches are forbidden."}


def environment_info(task, measure) -> dict:
    return {**task.manifest["native"]["candidate_image"], "judge": task.manifest["native"]["judge_image"],
            "limits": measure.to_dict(), "protocol": "isolated-function-timing-v1", "threads": 1}


def evaluate(task, code, dataset, measure, limits, *, run_id=None, candidate_id=None, measure_timing=True,
             baseline_code=None, deadline=None):
    from ..evaluator import Evaluation
    started, t0 = db.now(), time.perf_counter()
    ev = Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "pending", False, None, None, None, None, None, None, None)
    records = native.cases(task, dataset)
    settings = task.manifest["native"]
    samples, measured, judged = [], {"baseline": [], "candidate": []}, {"baseline": [], "candidate": []}
    try:
        for i, case in enumerate(records):
            order = (("baseline", baseline_code or task.initial_code.encode()), ("candidate", code)) if measure_timing else (("candidate", code),)
            if measure_timing and i % 2:
                order = tuple(reversed(order))
            for who, src in order:
                timeout = native.remaining_timeout(deadline, limits.measurement_timeout_s)
                if timeout <= 0:
                    ev.status = "budget_exhausted"
                    return ev
                request = {"problem": case["problem"], "repeats": measure.repeats if measure_timing else 1}
                sample = executor.run_sample(src, json.dumps(request).encode(), timeout, measure,
                    image=settings["candidate_image"]["image_id"], harness="/opt/routeevo/scientific_harness.py")
                samples.append({"who": who, "case": case["id"], **sample.summary()})
                if sample.status != "ok":
                    ev.status = "baseline_failed" if who == "baseline" else sample.status
                    ev.correct = False if who == "candidate" else None
                    ev.detail["failure"] = {"category": ev.status, "case": case["id"], "stderr_tail": sample.stderr_tail}
                    return ev
                try:
                    data = json.loads(sample.stdout)
                    times = data["times_s"]
                    if len(times) != request["repeats"] or len(data["solutions"]) != request["repeats"] + 1 or any(not native.finite_number(t) or t <= 0 for t in times):
                        raise ValueError("invalid function measurement")
                except (ValueError, KeyError, TypeError) as exc:
                    ev.status = "format_error" if who == "candidate" else "baseline_failed"
                    ev.detail["failure"] = {"category": ev.status, "message": str(exc)}
                    return ev
                measured[who].append(times)
                judged[who].append({"problem": case["problem"], "solutions": data["solutions"]})
        ev.executed = True
        for who in ("candidate", "baseline"):
            if not judged[who]:
                continue
            timeout = native.remaining_timeout(deadline, 120)
            if timeout <= 0:
                ev.status = "budget_exhausted"
                return ev
            results = native.worker(settings["judge_image"]["image_id"], "/opt/routeevo/algotune_worker.py",
                                     {"operation": "judge", "cases": judged[who]}, timeout=timeout)["cases"]
            correct = len(results) == len(records) and all(x["correct"] for x in results)
            if who == "candidate":
                ev.format_ok, ev.correct = True, correct
                ev.detail.update(case_count=len(records), passed_cases=sum(x["correct"] for x in results))
            if not correct:
                ev.status = "wrong_output" if who == "candidate" else "baseline_failed"
                ev.detail["failure"] = {"category": ev.status, "message": "upstream checker rejected one or more measurements"}
                return ev
        ev.status = "passed"
        if measure_timing:
            cs = [sum(xs) for xs in zip(*measured["candidate"])]
            bs = [sum(xs) for xs in zip(*measured["baseline"])]
            ev.candidate_median_s, ev.baseline_median_s = statistics.median(cs), statistics.median(bs)
            ev.speedup = ev.baseline_median_s / ev.candidate_median_s
            ev.improved = max(cs) < min(bs)
            ev.goal_met = ev.improved and ev.speedup >= task.target_min_speedup
            ev.detail["timing"] = {"candidate_s": cs, "baseline_s": bs, "candidate_min_max_s": [min(cs), max(cs)],
                "baseline_min_max_s": [min(bs), max(bs)], "method": "one warm-up + repeated solve calls per case; fresh globals/input; imports and serialization excluded"}
        return ev
    except (RuntimeError, ValueError, KeyError) as exc:
        ev.status = "budget_exhausted" if deadline is not None and time.perf_counter() >= deadline else "checker_error"
        ev.detail["failure"] = {"category": ev.status, "message": str(exc)}
        return ev
    finally:
        ev.detail["samples"] = samples
        ev.detail["container_ready_latency_s"] = sum(s.get("ready_latency_s") or 0 for s in samples)
        native.persist(task, ev, code, started, t0, run_id, candidate_id)
