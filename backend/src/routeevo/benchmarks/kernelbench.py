"""Pinned KernelBench tasks with isolated GPU execution through a trusted host worker."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time
import uuid

from .. import config, db, taskpkg
from . import native
from .native import MIN_MATCHES, buckets, compatible

SOURCE_REVISION = "129232ea3c4cfa05c2dd5473bdb935d6246dc84b"
SUPPORTED = {"1_Square_matrix_multiplication_": "963a3f87b1f98a7636c96a7f8284b3b7b483f96b"}


def call_worker(command: list[str], request: dict, timeout: float) -> dict:
    p = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"GPU worker failed ({p.returncode}): {p.stderr[-4000:]}")
    result = json.loads(p.stdout)
    if not isinstance(result, dict) or "status" not in result:
        raise ValueError("invalid GPU worker response")
    return result


def initial_program(source: str) -> str:
    class Rename(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            if node.name == "Model":
                node.name = "ModelNew"
            return self.generic_visit(node)

        def visit_Name(self, node):
            if node.id == "Model":
                node.id = "ModelNew"
            return node
    return ("# KernelBench: Copyright (c) 2023 Anne Ouyang, Simon Guo, Azalia Mirhoseini\n"
            "# Scaling Intelligence Lab, Stanford University. See UPSTREAM_LICENSE.txt.\n" +
            ast.unparse(ast.fix_missing_locations(Rename().visit(ast.parse(source)))) + "\n")


def import_problem(problem: str, *, split: str, source: Path | None, worker_command: str, image: str,
                   dev_cases: int = 2, final_cases: int = 5, task_id: str | None = None) -> taskpkg.Task:
    if problem not in SUPPORTED:
        raise ValueError(f"supported initial KernelBench subset: {list(SUPPORTED)}")
    command = json.loads(worker_command)
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("worker command must be a nonempty JSON string argv")
    if min(dev_cases, final_cases) < 1:
        raise ValueError("case counts must be positive")
    if source is None:
        source = native.fetch(f"https://raw.githubusercontent.com/ScalingIntelligence/KernelBench/{SOURCE_REVISION}/KernelBench/level1/{problem}.py",
                              config.VAR_DIR / "benchmarks" / "kernelbench" / SOURCE_REVISION / f"{problem}.py")
    raw = source.read_bytes()
    if hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != SUPPORTED[problem]:
        raise ValueError("KernelBench reference does not match the pinned upstream blob")
    license_path = native.fetch(f"https://raw.githubusercontent.com/ScalingIntelligence/KernelBench/{SOURCE_REVISION}/LICENSE",
                                config.VAR_DIR / "benchmarks" / "kernelbench" / SOURCE_REVISION / "LICENSE")
    environment = call_worker(command, {"operation": "environment", "image": image}, 30)
    if environment["status"] != "ok":
        raise RuntimeError(f"GPU environment unavailable: {environment}")
    records = [{"id": str(i), "seed": 1729 + i} for i in range(dev_cases + final_cases)]
    contract = ("KernelBench level 1. Submit a Python module defining ModelNew with the same constructor and forward "
                "interface as the initial ModelNew. Torch and CUDA C++ load_inline are available. Target NVIDIA compute "
                "capability 7.5, float32, TF32 disabled. All outputs must match the reference (atol=rtol=1e-4); "
                "every warm-up and measured output is checked in a separate container. CUDA events measure forward "
                "after synchronization; compilation, transfers and output checks count toward total research time. "
                "Current Triton is not supported on this GPU. Do not read stdin, change timers or write evaluation files.\n")
    return native.package("kernelbench", problem, split,
        {"repository": "ScalingIntelligence/KernelBench", "revision": SOURCE_REVISION,
         "blob": SUPPORTED[problem], "reference_sha256": taskpkg.sha256_bytes(raw), "license": "MIT"},
        contract, initial_program(raw.decode()), records[:dev_cases], records[dev_cases:],
        objective={"metric": "speedup", "direction": "maximize"}, settings={"worker_command": command,
            "image_id": image, "environment": environment, "allowed_imports": ["torch", "numpy"], "candidate_interface": "ModelNew"},
        task_id=task_id, extra_files={"reference.py": raw, "UPSTREAM_LICENSE.txt": license_path.read_bytes()})


def environment_info(task, measure) -> dict:
    settings = task.manifest["native"]
    current = call_worker(settings["worker_command"], {"operation": "environment", "image": settings["image_id"]}, 30)
    if current != settings["environment"]:
        raise RuntimeError("GPU environment changed since task import; import a new frozen task")
    return {"image_id": settings["image_id"], "gpu_worker": current, "protocol": "kernel-isolated-v1"}


def presentation(manifest: dict) -> dict:
    return {"title": f"KernelBench · {manifest['problem']['key']}",
        "workload": f"{manifest['problem']['key']} · float32 · {manifest['dev_params']['cases']} dev seeds",
        "baseline": "固定版本 PyTorch Model，改名 ModelNew", "validation": "隔离输出校验；CUDA events 计时；固定 GPU",
        "agent_notes": "Optimize ModelNew.forward using PyTorch or CUDA C++; do not use Triton on compute capability 7.5. "
                       "No cProfile tool. Use validation feedback; every measured output is checked separately."}


def evaluate(task, code, dataset, measure, limits, *, run_id=None, candidate_id=None, measure_timing=True,
             baseline_code=None, deadline=None):
    from ..evaluator import Evaluation
    started, t0 = db.now(), time.perf_counter()
    ev = Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "pending", False, None, None, None, None, None, None, None)
    settings = task.manifest["native"]
    timeout = native.remaining_timeout(deadline, max(120, limits.measurement_timeout_s * len(native.cases(task, dataset)) * 2))
    try:
        if timeout <= 0:
            ev.status = "budget_exhausted"
            return ev
        result = call_worker(settings["worker_command"], {"operation": "evaluate", "image": settings["image_id"],
            "code": code.decode(), "initial": task.initial_code, "reference": (task.dir / "reference.py").read_text(),
            "seeds": [x["seed"] for x in native.cases(task, dataset)], "repeats": measure.repeats if measure_timing else 1,
            "timeout_s": timeout}, timeout + 15)
        ev.status = result["status"]
        ev.executed = ev.status in ("passed", "wrong_output")
        ev.format_ok = ev.executed
        ev.correct = ev.status == "passed"
        ev.detail["case_count"] = len(native.cases(task, dataset))
        ev.detail["passed_cases"] = sum(x.get("correct", False) for x in result.get("cases", []))
        if ev.status != "passed":
            ev.detail["failure"] = {"category": ev.status, **result.get("failure", {})}
            return ev
        if len(result["cases"]) != ev.detail["case_count"]:
            raise ValueError("GPU worker omitted cases")
        ev.detail["samples"] = result["cases"]
        if measure_timing:
            cs = [sum(x) for x in zip(*(c["candidate"]["times_s"] for c in result["cases"]))]
            bs = [sum(x) for x in zip(*(c["baseline"]["times_s"] for c in result["cases"]))]
            ev.candidate_median_s, ev.baseline_median_s = statistics.median(cs), statistics.median(bs)
            ev.speedup = ev.baseline_median_s / ev.candidate_median_s
            ev.improved = max(cs) < min(bs)
            ev.goal_met = ev.improved and ev.speedup >= task.target_min_speedup
            ev.detail["timing"] = {"candidate_s": cs, "baseline_s": bs, "candidate_min_max_s": [min(cs), max(cs)],
                                  "baseline_min_max_s": [min(bs), max(bs)], "method": "CUDA events, synchronized; every output independently checked"}
        return ev
    except subprocess.TimeoutExpired:
        ev.status = "timeout"
        ev.detail["failure"] = {"category": "timeout", "message": "GPU worker exceeded its request deadline"}
        return ev
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        ev.status = "sandbox_error"
        ev.detail["failure"] = {"category": ev.status, "message": str(exc)}
        return ev
    finally:
        native.persist(task, ev, code, started, t0, run_id, candidate_id)
