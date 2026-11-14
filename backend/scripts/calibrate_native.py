"""Calibrate AlgoTune dev timing with fixed programs and no model requests.

Run from backend with ``uv run python scripts/calibrate_native.py --help``.
The matrix preserves the evaluator's correctness checks and strict selection rule.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from functools import cache
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
from unittest.mock import patch

from routeevo import config, db, taskpkg
from routeevo.benchmarks import algotune
from routeevo.sandbox import executor


ROOT = Path(__file__).resolve().parents[2]


def load_dev_task(task_id: str) -> taskpkg.Task:
    directory = config.TASK_DATA_DIR / task_id
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["task_id"] != task_id or manifest["family"] != "algotune":
        raise ValueError("calibration requires an existing AlgoTune task")
    row = db.one("SELECT family, split, manifest_json, manifest_sha256 FROM tasks WHERE task_id = ?", (task_id,))
    manifest_sha = taskpkg.sha256_bytes(json.dumps(manifest, sort_keys=True).encode())
    if (row is None or row["family"] != "algotune" or row["split"] != manifest["split"] or
            json.loads(row["manifest_json"]) != manifest or row["manifest_sha256"] != manifest_sha):
        raise ValueError("task manifest does not match its immutable SQLite registration")
    # This verifies every package file, including the reserved final data, without evaluating final inputs.
    return taskpkg.load(task_id, verify=True)


def host_affinity() -> list[int] | None:
    get_affinity = getattr(os, "sched_getaffinity", None)
    return sorted(get_affinity(0)) if get_affinity is not None else None


@cache
def docker_cpu_ids() -> list[int]:
    try:
        count = int(subprocess.check_output(
            ["docker", "info", "--format", "{{.NCPU}}"], text=True, timeout=15).strip())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError(f"could not determine Docker VM CPU count: {exc}") from exc
    if count < 1:
        raise RuntimeError(f"Docker reported an invalid CPU count: {count}")
    return list(range(count))


def available_cpuset_cpus() -> list[int]:
    affinity = host_affinity()
    return affinity if affinity is not None else docker_cpu_ids()


def environment() -> dict:
    cpus = {}
    for path in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*"), key=lambda p: int(p.name[3:])):
        values = {}
        for name in ("cpu_capacity", "topology/core_id", "cpufreq/scaling_governor",
                     "cpufreq/cpuinfo_max_freq", "cpufreq/base_frequency", "cpufreq/scaling_cur_freq"):
            field = path / name
            if field.exists():
                values[name] = field.read_text().strip()
        cpus[path.name] = values
    affinity = host_affinity()
    system = platform.system()
    return {"platform": platform.platform(), "host_python": platform.python_version(),
            "host_logical_cpu_count": os.cpu_count(), "host_affinity": affinity,
            "host_affinity_supported": affinity is not None,
            "cpuset_cpu_ids": available_cpuset_cpus(),
            "cpuset_scope": "docker_vm_vcpu" if affinity is None else "host_cpu",
            "physical_core_exclusive": False,
            "cpu_topology_source": "linux_sysfs" if cpus else None,
            "load_average": list(os.getloadavg()), "cpus": cpus,
            "notes": (["Docker VM vCPU affinity does not identify or reserve a physical Apple Silicon core."]
                      if system == "Darwin" else [])}


def slowed_program(code: bytes, delay_ms: float) -> bytes:
    return code + ("\n\nfrom time import sleep as _calibration_sleep\n"
                   "_calibration_original_solve = solve\n"
                   "def solve(problem):\n"
                   "    answer = _calibration_original_solve(problem)\n"
                   f"    _calibration_sleep({delay_ms / 1000!r})\n"
                   "    return answer\n").encode()


def check_affinity(task, measure: config.MeasureConfig) -> dict:
    code = b"import os\ndef solve(problem):\n    return sorted(os.sched_getaffinity(0))\n"
    started_at = db.now()
    sample = executor.run_sample(code, json.dumps({"problem": None, "repeats": 2,
                                                  "warmups": measure.function_warmups}).encode(),
                                 config.RunLimits().measurement_timeout_s, measure,
                                 image=task.manifest["native"]["candidate_image"]["image_id"],
                                 harness="/opt/routeevo/scientific_harness.py")
    record = {"started_at": started_at, "ended_at": db.now(), **sample.summary()}
    if sample.status != "ok":
        raise RuntimeError(f"affinity probe failed: {sample.status}: {sample.stderr_tail}")
    payload = json.loads(sample.stdout)
    expected = [int(measure.cpuset_cpus)]
    record.update(requested_affinity=expected, observed_affinities=payload["solutions"],
                  warmup_count=payload.get("warmup_count", 1))
    if record["warmup_count"] != measure.function_warmups or len(payload["solutions"]) != 2 + measure.function_warmups:
        raise RuntimeError("container warm-up count does not match the calibration configuration")
    if any(observed != expected for observed in payload["solutions"]):
        raise RuntimeError(f"container affinity does not match requested CPU: {record}")
    return record


def matrix(rounds: int, pinned_only: bool) -> list[dict]:
    steps = []
    for round_index in range(rounds):
        names = ("pinned",) if pinned_only else (
            ("default", "pinned") if round_index % 2 == 0 else ("pinned", "default"))
        for name in names:
            steps.append({"kind": "self", "configuration": name, "round": round_index + 1,
                          "baseline": "original", "candidate": "original", "expected_improved": False})
    steps.extend([
        {"kind": "positive_control", "configuration": "pinned", "round": 1,
         "baseline": "delayed", "candidate": "original", "expected_improved": True},
        {"kind": "negative_control", "configuration": "pinned", "round": 1,
         "baseline": "original", "candidate": "delayed", "expected_improved": False},
    ])
    return steps


def evaluate_step(task, step: dict, programs: dict, measure: config.MeasureConfig) -> dict:
    raw_samples = []
    original_run_sample = executor.run_sample

    def record_sample(code, input_bytes, timeout_s, measure, *args, **kwargs):
        started_at = db.now()
        sample = original_run_sample(code, input_bytes, timeout_s, measure, *args, **kwargs)
        record = {"sequence": len(raw_samples) + 1, "started_at": started_at, "ended_at": db.now(),
                  "code_sha256": taskpkg.sha256_bytes(code), **sample.summary()}
        if sample.status == "ok":
            payload = json.loads(sample.stdout)
            record.update(times_s=payload["times_s"], initialization_s=payload["initialization_s"],
                          solution_count=len(payload["solutions"]), warmup_count=payload.get("warmup_count", 1))
        raw_samples.append(record)
        return sample

    started_at, before = db.now(), environment()
    # Observe the existing harness response; the evaluator still judges every output.
    with patch.object(executor, "run_sample", record_sample):
        result = algotune.evaluate(task, programs[step["candidate"]], "dev", measure, config.RunLimits(),
                                   baseline_code=programs[step["baseline"]])
    for record, sample in zip(raw_samples, result.detail["samples"], strict=True):
        record.update(who=sample["who"], case=sample["case"])
    return {**step, "started_at": started_at, "ended_at": db.now(), "environment_before": before,
            "environment_after": environment(), "measure": measure.to_dict(), "evaluation": asdict(result),
            "raw_samples": raw_samples,
            "expected_outcome_observed": result.status == "passed" and result.improved == step["expected_improved"]}


def summarize(results: list[dict]) -> dict:
    summary = {}
    for name in ("default", "pinned"):
        rows = [r["evaluation"] for r in results if r["kind"] == "self" and r["configuration"] == name]
        complete = [r for r in rows if r["status"] == "passed"]
        spreads, first_relative = [], []
        for row in complete:
            for role in ("baseline", "candidate"):
                times = row["detail"]["timing"][f"{role}_s"]
                spreads.append((max(times) - min(times)) / statistics.median(times))
                first_relative.append(times[0] / statistics.median(times[1:]) - 1)
        summary[name] = {"self_comparisons": len(rows), "passed": len(complete),
                         "speedups": [r["speedup"] for r in complete],
                         "strict_false_improvements": sum(r["improved"] is True for r in complete),
                         "median_range_over_median": statistics.median(spreads) if spreads else None,
                         "median_first_vs_rest": statistics.median(first_relative) if first_relative else None}
    summary["controls"] = [{"kind": r["kind"], "expected_outcome_observed": r["expected_outcome_observed"],
                            "speedup": r["evaluation"]["speedup"]} for r in results if r["kind"] != "self"]
    return summary


def write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--cpuset-cpus", required=True, help="one chosen CPU for the pinned configuration")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--pinned-only", action="store_true", help="only compare the pinned configuration")
    parser.add_argument("--control-delay-ms", type=float, default=3.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true", help="write the frozen matrix without executing containers")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10 or not 2 <= args.repeats <= 100 or not 0 < args.control_delay_ms <= 100:
        parser.error("rounds must be 1..10, repeats 2..100, and control delay 0..100 ms")
    if not 1 <= args.warmups <= 20:
        parser.error("warmups must be 1..20")
    if not args.cpuset_cpus.isdecimal() or int(args.cpuset_cpus) not in available_cpuset_cpus():
        parser.error("cpuset-cpus must name one CPU available to the Docker execution environment")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    task = load_dev_task(args.task_id)
    registered = db.one("SELECT manifest_sha256 FROM tasks WHERE task_id = ?", (task.task_id,))
    measures = {"default": config.MeasureConfig(repeats=args.repeats, function_warmups=args.warmups),
                "pinned": config.MeasureConfig(repeats=args.repeats, function_warmups=args.warmups,
                                               cpuset_cpus=args.cpuset_cpus)}
    original = task.initial_code.encode()
    programs = {"original": original, "delayed": slowed_program(original, args.control_delay_ms)}
    source_paths = [Path(__file__), ROOT / "backend/src/routeevo/config.py",
                    ROOT / "backend/src/routeevo/sandbox/executor.py",
                    ROOT / "backend/src/routeevo/benchmarks/algotune.py",
                    ROOT / "backend/src/routeevo/benchmarks/native_tools/scientific_harness.py"]
    result = {"schema": "native-calibration-v1", "status": "planned", "created_at": db.now(),
              "task_id": task.task_id, "dataset": "dev", "model_requests": 0, "warmup_count": args.warmups,
              "control_delay_ms": args.control_delay_ms,
              "control_method": "sleep after the original solve; adds at least the requested wall time per case",
              "task_manifest_sha256": taskpkg.sha256_file(task.dir / "manifest.json"),
              "task_manifest_canonical_sha256": registered["manifest_sha256"],
              "task_package_files": {key: meta["sha256"] for key, meta in task.manifest["files"].items()},
              "dev_sha256": task.manifest["files"]["dev_input"]["sha256"],
              "candidate_image": task.manifest["native"]["candidate_image"],
              "judge_image": task.manifest["native"]["judge_image"],
              "program_sha256": {name: taskpkg.sha256_bytes(code) for name, code in programs.items()},
              "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_sha256": {str(p.relative_to(ROOT)): taskpkg.sha256_file(p) for p in source_paths},
              "environment": environment(), "measures": {k: v.to_dict() for k, v in measures.items()},
              "matrix": matrix(args.rounds, args.pinned_only), "results": []}
    write_result(args.output, result)
    if args.plan_only:
        print(f"wrote {len(result['matrix'])}-comparison plan: {args.output}")
        return
    result["status"] = "running"
    try:
        result["affinity_probe"] = check_affinity(task, measures["pinned"])
        write_result(args.output, result)
        for sequence, step in enumerate(result["matrix"], 1):
            measured = evaluate_step(task, step, programs, measures[step["configuration"]])
            measured["sequence"] = sequence
            result["results"].append(measured)
            result["summary"] = summarize(result["results"])
            write_result(args.output, result)
            print(json.dumps({"sequence": sequence, "kind": step["kind"], "configuration": step["configuration"],
                              "status": measured["evaluation"]["status"], "speedup": measured["evaluation"]["speedup"],
                              "improved": measured["evaluation"]["improved"]}), flush=True)
            if measured["evaluation"]["status"] != "passed":
                raise RuntimeError(f"calibration comparison failed: {measured['evaluation']['status']}")
            if not measured["expected_outcome_observed"]:
                raise RuntimeError(f"calibration outcome did not match the frozen expectation: {step['kind']}")
        result["status"] = "completed"
    except BaseException as exc:
        result.update(status="failed", failure=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        result["ended_at"] = db.now()
        write_result(args.output, result)


if __name__ == "__main__":
    main()
