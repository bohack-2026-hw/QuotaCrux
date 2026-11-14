"""Shared file, container and result handling for the three research benchmarks."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import httpx

from .. import config, db, taskpkg

TOOLS = Path(__file__).with_name("native_tools")
REVISION = "research-benchmarks-v1"
MIN_MATCHES = 1


def fetch(url: str, path: Path, *, max_bytes: int = 32 * 1024 * 1024) -> Path:
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            try:
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"download exceeds {max_bytes} bytes: {url}")
                    f.write(chunk)
                f.flush()
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
    return path


def package(family: str, problem: str, split: str, source: dict, contract: str, initial: str,
            dev: list[dict], final: list[dict], *, objective: dict, settings: dict,
            task_id: str | None = None, extra_files: dict[str, bytes] | None = None) -> taskpkg.Task:
    if not dev or not final:
        raise ValueError("dev and final must both contain cases")
    digest = hashlib.sha256(json.dumps([REVISION, source, settings, dev, final, contract, initial, objective,
        {name: taskpkg.sha256_bytes(data) for name, data in (extra_files or {}).items()}], sort_keys=True).encode()).hexdigest()[:10]
    task_id = task_id or f"{family}-{problem}-{split}-{digest}"
    if not task_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for c in task_id):
        raise ValueError("task id must contain only letters, digits, '.', '_' and '-'")
    if task_id in (".", ".."):
        raise ValueError("invalid task id")
    config.TASK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".native-", dir=config.TASK_DATA_DIR))
    blobs = {"contract": ("contract.txt", contract.encode()), "initial": ("initial.py", initial.encode()),
             "examples": ("examples.json", b"[]"),
             "dev_profile": ("dev_profile.json", json.dumps({"problem": problem, "cases": len(dev),
                 "memory_key": digest, "settings": {k: v for k, v in settings.items() if k not in ("seeds",)}}).encode())}
    for name, cases in (("dev", dev), ("final", final)):
        blobs[f"{name}_input"] = (f"{name}.json", json.dumps(cases, allow_nan=False).encode())
        blobs[f"{name}_expected"] = (f"{name}-expected.json", b"[]")
    for name, data in (extra_files or {}).items():
        blobs[name] = (name, data)
    files = {key: taskpkg._write(tmp / name, data) for key, (name, data) in blobs.items()}
    manifest = {"task_id": task_id, "family": family, "split": split, "adapter_version": REVISION,
                "source": source, "problem": {"key": problem, "title": problem}, "files": files,
                "target": {"min_speedup": None if objective["metric"] == "score" else 1.10, **objective},
                "dev_params": {"cases": len(dev)}, "final_params": {"cases": len(final)}, "native": settings,
                "selection": {"dev_cases": len(dev), "final_cases": len(final)}, "notes": "RouteEvo research subset"}
    try:
        return taskpkg.register_package(tmp, manifest, config.TASK_DATA_DIR)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def cases(task, dataset: str) -> list[dict]:
    if dataset not in ("dev", "final"):
        raise ValueError(dataset)
    return json.loads(task.dataset(dataset)[0].read_text())


def build_image(context: Path, prefix: str) -> dict:
    h = hashlib.sha256()
    for path in sorted(context.rglob("*")):
        if path.is_file():
            h.update(str(path.relative_to(context)).encode())
            h.update(path.read_bytes())
    tag = f"routeevo-{prefix}:{h.hexdigest()[:12]}"
    inspect = ["docker", "image", "inspect", tag, "--format", "{{.Id}}"]
    p = subprocess.run(inspect, capture_output=True, text=True)
    if p.returncode:
        p = subprocess.run(["docker", "build", "-t", tag, str(context)], capture_output=True, text=True, timeout=900)
        if p.returncode:
            raise RuntimeError(f"{prefix} image build failed: {p.stderr[-4000:]}\n{p.stdout[-2000:]}")
        p = subprocess.run(inspect, capture_output=True, text=True, check=True)
    return {"image_tag": tag, "image_id": p.stdout.strip()}


def worker(image: str, script: str, payload: dict, *, timeout: float = 120, memory: str = "2g") -> dict:
    """Trusted generator/checker container; candidate code never shares this filesystem."""
    name = f"routeevo-judge-{uuid.uuid4().hex[:12]}"
    cmd = ["docker", "run", "--rm", "-i", "--name", name, "--network", "none", "--read-only",
           "--cpus", "1", "--memory", memory, "--memory-swap", memory, "--pids-limit", "64",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534",
           "--tmpfs", "/tmp:rw,nosuid,size=256m,mode=1777", "-e", "OPENBLAS_NUM_THREADS=1",
           "-e", "OMP_NUM_THREADS=1", image, "python", "-B", script]
    try:
        p = subprocess.run(cmd, input=json.dumps(payload, allow_nan=False), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        raise RuntimeError(f"benchmark checker/generator exceeded {timeout}s") from None
    if p.returncode:
        raise RuntimeError(f"benchmark checker/generator failed ({p.returncode}): {p.stderr[-3000:]}")
    result = json.loads(p.stdout)
    if not isinstance(result, dict):
        raise ValueError("benchmark worker must return an object")
    return result


def persist(task, ev, code, started: str, t0: float, run_id, candidate_id):
    ev.started_at, ev.ended_at = started, db.now()
    ev.detail.update(duration_s=round(time.perf_counter() - t0, 3),
                     dataset_sha256=task.manifest["files"][f"{ev.dataset}_input"]["sha256"],
                     candidate_sha256=taskpkg.sha256_bytes(code))
    db.insert("evaluations", {"evaluation_id": ev.evaluation_id, "task_id": task.task_id,
        "run_id": run_id, "candidate_id": candidate_id, "dataset": ev.dataset,
        "dataset_sha256": ev.detail["dataset_sha256"], "status": ev.status, "executed": int(ev.executed),
        **{k: None if getattr(ev, k) is None else int(getattr(ev, k)) for k in ("format_ok", "correct", "improved", "goal_met")},
        "speedup": ev.speedup, "candidate_median_s": ev.candidate_median_s, "baseline_median_s": ev.baseline_median_s,
        "detail_json": db.dumps(ev.detail), "evaluator_version": REVISION,
        "started_at": ev.started_at, "ended_at": ev.ended_at})
    return ev


def remaining_timeout(deadline: float | None, timeout: float) -> float:
    return timeout if deadline is None else max(0.0, min(timeout, deadline - time.perf_counter()))


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def buckets(profile: dict) -> dict:
    return {"problem": profile["memory_key"]}


def compatible(current: dict, theirs: dict) -> bool:
    return current == theirs
