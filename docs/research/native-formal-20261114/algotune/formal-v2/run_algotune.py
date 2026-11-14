"""Preflight and run the frozen Mac AlgoTune plan one formal slot at a time."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


SOURCE_PATHS = (
    "backend/src/routeevo",
    "backend/pyproject.toml",
    "backend/uv.lock",
)
FATAL_STOP_REASONS = {
    "environment_error",
    "internal_error",
    "model_api_error",
    "user_stopped",
}
HOSTED_ENV = (
    "QWEN_API_KEY",
    "QWEN_BASE_URL",
    "QWEN_MODEL",
    "QWEN_RESPONSE_FORMAT",
    "QWEN_ENABLE_THINKING",
    "QWEN_MAX_OUTPUT_TOKENS",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def docker_runtime() -> dict:
    values = subprocess.check_output(
        [
            "docker",
            "info",
            "--format",
            "{{.OSType}}\t{{.Architecture}}\t{{.NCPU}}\t{{.MemTotal}}\t{{.ServerVersion}}",
        ],
        text=True,
    ).strip().split("\t")
    if len(values) != 5:
        raise RuntimeError("could not identify the Docker server runtime")
    return {
        "os": values[0],
        "architecture": values[1],
        "cpus": int(values[2]),
        "memory_bytes": int(values[3]),
        "version": values[4],
    }


def check_source(manifest: dict) -> None:
    code_sha = manifest["code_sha"]
    subprocess.run(["git", "cat-file", "-e", f"{code_sha}^{{commit}}"], check=True)
    if subprocess.run(["git", "merge-base", "--is-ancestor", code_sha, "HEAD"]).returncode:
        raise RuntimeError("frozen source SHA is not an ancestor of the checkout")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("source checkout is not clean")
    changed = git("diff", "--name-only", code_sha, "HEAD", "--", *SOURCE_PATHS)
    if changed:
        raise RuntimeError(f"runtime source differs from frozen SHA: {changed}")
    if sha256(Path(__file__)) != manifest["executor_sha256"]:
        raise RuntimeError("AlgoTune executor differs from frozen bytes")


def check_plan(manifest: dict, tasks: dict) -> None:
    from routeevo.research_compare import validate_plan

    central_path = Path(manifest["central_plan_path"])
    if sha256(central_path) != manifest["central_plan_sha256"]:
        raise RuntimeError("central plan differs from the frozen bytes")
    central = json.loads(central_path.read_text())
    entries = [entry for entry in central["entries"] if entry["host"] == "snowball-mac"]
    plan = manifest["algotune_plan"]
    if len(entries) != len(plan):
        raise RuntimeError("Mac plan length differs from the central plan")
    by_key = {binding["task_key"]: task_id for task_id, binding in tasks.items()}
    for expected, actual in zip(entries, plan, strict=True):
        if {
            "seq": expected["slot"],
            "task_id": by_key[expected["task_key"]],
            "repeat": expected["repeat"],
            "mode": expected["mode"],
        } != {key: actual[key] for key in ("seq", "task_id", "repeat", "mode")}:
            raise RuntimeError(f"slot {expected['slot']} differs from the central plan")
    validate_plan(plan, list(tasks))


def check_model(manifest: dict) -> list[str]:
    from routeevo import config

    models = config.default_model_configs()
    missing = [name for name in HOSTED_ENV if not os.environ.get(name)]
    if os.environ.get("QWEN_REASONING_EFFORT") or os.environ.get("QWEN_TEMPERATURE"):
        raise RuntimeError("reasoning effort and temperature must remain unset for this freeze")
    if not missing and models["small"].public_dict() != manifest["model"]:
        raise RuntimeError("model configuration differs from the frozen manifest")
    return [f"missing hosted setting: {name}" for name in missing]


def check_tasks(args, manifest: dict) -> dict:
    from routeevo import config, db, taskpkg
    from routeevo.agent import actions, prompt

    if config.VAR_DIR != args.root:
        raise RuntimeError("ROUTEEVO_VAR_DIR is not the registered absolute task directory")
    schema_sha = hashlib.sha256(json.dumps(actions.ACTION_SCHEMA, sort_keys=True).encode()).hexdigest()
    if schema_sha != manifest["action_schema_sha256"]:
        raise RuntimeError("action schema differs from the freeze")
    if prompt.PROMPT_VERSION != manifest["prompt_version"]:
        raise RuntimeError("prompt version differs from the freeze")
    measure = config.MeasureConfig(**manifest["measure"])
    loaded = {}
    for task_id, binding in manifest["tasks"].items():
        task = taskpkg.load(task_id)
        row = db.one("SELECT manifest_sha256 FROM tasks WHERE task_id=?", (task_id,))
        if row is None or row["manifest_sha256"] != binding["manifest_sha256"]:
            raise RuntimeError(f"task manifest differs from freeze: {task_id}")
        if task.adapter.environment_info(task, measure) != binding["environment"]:
            raise RuntimeError(f"container environment differs from freeze: {task_id}")
        for mode, expected in binding["prompt_sha256"].items():
            actual = hashlib.sha256(prompt.system_prompt(task, mode).encode()).hexdigest()
            if actual != expected:
                raise RuntimeError(f"system prompt differs from freeze: {task_id}/{mode}")
        loaded[task_id] = task
    return loaded


def preflight(args, manifest: dict, *, require_ready: bool) -> tuple[dict, dict]:
    if not args.root.is_absolute() or not args.out.is_absolute():
        raise RuntimeError("--root and --out must be absolute paths")
    check_source(manifest)
    blockers = check_model(manifest)
    tasks = check_tasks(args, manifest)
    check_plan(manifest, manifest["tasks"])
    if docker_runtime() != manifest["docker_runtime"]:
        raise RuntimeError("Docker VM resources differ from the frozen runtime")
    if manifest["freeze_status"] != "ready":
        blockers.append(f"freeze status is {manifest['freeze_status']}")
    calibration = manifest["calibration"]
    if not calibration["accepted"]:
        blockers.append("timing-v2 calibration is not accepted")
    else:
        evidence = Path(calibration["evidence_path"])
        if sha256(evidence) != calibration["evidence_sha256"]:
            raise RuntimeError("accepted calibration evidence differs from freeze")
    current_load = os.getloadavg()[0]
    if current_load > manifest["host_policy"]["max_load_1m_at_start"]:
        blockers.append(
            f"host load {current_load:.2f} exceeds "
            f"{manifest['host_policy']['max_load_1m_at_start']:.2f}"
        )
    result = {
        "status": "ready" if not blockers else "blocked",
        "code_sha": manifest["code_sha"],
        "plan_id": manifest["plan_id"],
        "tasks": list(tasks),
        "slots": len(manifest["algotune_plan"]),
        "model_calls": 0,
        "final_evaluations": 0,
        "blockers": blockers,
    }
    if require_ready and blockers:
        raise RuntimeError("formal execution blocked: " + "; ".join(blockers))
    return tasks, result


def worker(args, manifest: dict) -> None:
    from routeevo import config, research_compare

    tasks, _ = preflight(args, manifest, require_ready=True)
    step = next((item for item in manifest["algotune_plan"] if item["seq"] == args.seq), None)
    if step is None:
        raise RuntimeError(f"unknown formal slot: {args.seq}")
    output = args.out / "slots" / f"{args.seq:02d}.json"
    if output.exists():
        raise RuntimeError("slot already has evidence; do not replace or silently rerun")
    task = tasks[step["task_id"]]
    result = research_compare.execute(
        [task.task_id],
        limits=config.RunLimits(**manifest["limits"]),
        fixed_model="small",
        final_evaluation=True,
        measure=config.MeasureConfig(**manifest["measure"]),
        plan=[step],
        plan_id=manifest["plan_id"],
        pricing=manifest["pricing"],
        label=f"AlgoTune formal central slot {args.seq}",
    )
    write(output, result)
    row = result["runs"][0]
    print(
        json.dumps(
            {
                "seq": args.seq,
                "run_id": row.get("run_id"),
                "status": row["status"],
                "final_status": row["final_status"],
            }
        ),
        flush=True,
    )


def initial_result(manifest: dict) -> dict:
    return {
        "comparison_id": manifest["plan_id"],
        "plan_id": manifest["plan_id"],
        "protocol": manifest["protocol"],
        "label": "Mac AlgoTune formal 15-slot feedback comparison",
        "code_sha": manifest["code_sha"],
        "status": "running",
        "fair": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "final_evaluation": True,
        "price_snapshot": manifest["pricing"],
        "limits": manifest["limits"],
        "measure": manifest["measure"],
        "plan": manifest["algotune_plan"],
        "runs": [
            dict(step, status="not_run", final_status="not_run", dev_status="not_run")
            for step in manifest["algotune_plan"]
        ],
        "slots": [],
    }


def main(args, manifest: dict) -> None:
    from routeevo import research_compare
    from routeevo.research_views import comparison_summary

    _, report = preflight(args, manifest, require_ready=args.execute)
    if not args.execute:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    aggregate_path = args.out / f"{manifest['plan_id']}.json"
    if args.resume:
        if not aggregate_path.exists():
            raise RuntimeError("cannot resume without the existing aggregate evidence")
        out = json.loads(aggregate_path.read_text())
        if out.get("plan") != manifest["algotune_plan"] or out.get("code_sha") != manifest["code_sha"]:
            raise RuntimeError("existing aggregate differs from the frozen execution")
        out["status"] = "running"
        out.pop("ended_at", None)
    else:
        args.out.mkdir(parents=True, exist_ok=False)
        write(args.out / "frozen-manifest.json", manifest)
        out = initial_result(manifest)

    script = str(Path(__file__).resolve())
    started = time.monotonic()

    def save() -> None:
        research_compare.summarize(out)
        out.pop("cost", None)
        out["cost"] = comparison_summary(out)["cost"]
        write(aggregate_path, out)

    def launch(step: dict) -> dict:
        slot = args.out / "slots" / f"{step['seq']:02d}.json"
        if slot.exists():
            saved = json.loads(slot.read_text())
            return saved["runs"][0]
        logfile = args.out / "logs" / f"{step['seq']:02d}.log"
        logfile.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            script,
            "--root",
            str(args.root),
            "--manifest",
            str(args.manifest),
            "--out",
            str(args.out),
            "--worker",
            "--execute",
            "--seq",
            str(step["seq"]),
        ]
        with logfile.open("x") as log:
            process = subprocess.run(command, env=os.environ, stdout=log, stderr=subprocess.STDOUT)
        if not process.returncode and slot.exists():
            return json.loads(slot.read_text())["runs"][0]
        comparisons = sorted(
            (args.root / "comparisons").glob("research-*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in comparisons:
            partial = json.loads(path.read_text())
            if partial.get("plan_id") != manifest["plan_id"]:
                continue
            row = next((item for item in partial["runs"] if item["seq"] == step["seq"]), None)
            if row is not None:
                write(slot, partial)
                return dict(
                    row,
                    status="interrupted",
                    error=f"worker exited {process.returncode}; inspect {logfile}",
                )
        return dict(
            step,
            status="interrupted",
            final_status="not_run",
            dev_status="not_run",
            error=f"worker exited {process.returncode}; inspect {logfile}",
        )

    save()
    try:
        for step in manifest["algotune_plan"]:
            existing = next(row for row in out["runs"] if row["seq"] == step["seq"])
            if existing.get("status") != "not_run":
                continue
            slot_start = time.monotonic()
            result = launch(step)
            index = next(i for i, row in enumerate(out["runs"]) if row["seq"] == step["seq"])
            out["runs"][index] = result
            out["slots"].append(
                {
                    "seq": step["seq"],
                    "wall_clock_s": time.monotonic() - slot_start,
                    "status": result["status"],
                    "final_status": result.get("final_status"),
                }
            )
            save()
            print(
                json.dumps(
                    {
                        "slot": step["seq"],
                        "recorded": sum(row.get("status") != "not_run" for row in out["runs"]),
                        "status": result["status"],
                        "final_status": result.get("final_status"),
                        "elapsed_s": time.monotonic() - started,
                    }
                ),
                flush=True,
            )
            if result.get("error") or result.get("stop_reason") in FATAL_STOP_REASONS:
                out["status"] = "interrupted"
                break
        else:
            outcomes_ok = all(
                row.get("status") == "completed" and row.get("final_status") == "completed"
                for row in out["runs"]
            )
            out["status"] = "completed" if outcomes_ok else "failed"
    except BaseException:
        out["status"] = "interrupted"
        raise
    finally:
        out["ended_at"] = datetime.now(timezone.utc).isoformat()
        out["batch_wall_clock_s"] = out.get("batch_wall_clock_s", 0) + time.monotonic() - started
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--seq", type=int, help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    frozen = json.loads(arguments.manifest.read_text())
    if arguments.worker:
        worker(arguments, frozen)
    else:
        main(arguments, frozen)
