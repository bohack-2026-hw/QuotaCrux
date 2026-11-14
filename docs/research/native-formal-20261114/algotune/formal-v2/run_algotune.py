"""Preflight and run the frozen Mac AlgoTune plan one formal slot at a time."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import time


SOURCE_PATHS = (
    "backend/src/routeevo",
    "backend/scripts",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/.python-version",
)
EXPECTED_MANIFEST = Path(__file__).with_name("freeze-candidate.json").resolve()
FATAL_STOP_REASONS = {
    "environment_error",
    "internal_error",
    "model_api_error",
    "user_stopped",
}
FATAL_FINAL_STATUSES = {"sandbox_error", "baseline_failed", "checker_error"}
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def repository_root() -> Path:
    return Path(git("rev-parse", "--show-toplevel")).resolve()


def check_tracked(path: Path) -> Path:
    root = repository_root()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"frozen artifact is outside the repository: {path}") from exc
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(relative)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative.as_posix()}"])
    if resolved.read_bytes() != committed:
        raise RuntimeError(f"frozen artifact differs from HEAD: {relative}")
    return resolved


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


def check_image(image: dict) -> None:
    values = subprocess.check_output(
        [
            "docker",
            "image",
            "inspect",
            image["image_tag"],
            "--format",
            "{{.Id}}\t{{.Architecture}}\t{{.Os}}",
        ],
        text=True,
    ).strip().split("\t")
    if values != [image["image_id"], "arm64", "linux"]:
        raise RuntimeError(f"image identity or architecture differs: {image['image_tag']}")


def check_source(args, manifest: dict) -> None:
    if args.manifest.resolve() != EXPECTED_MANIFEST:
        raise RuntimeError("--manifest must name the repository's formal-v2 freeze manifest")
    check_tracked(args.manifest)
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


def check_plan(manifest: dict, tasks: dict) -> list[str]:
    from routeevo.research_compare import validate_plan

    central_path = check_tracked(repository_root() / manifest["central_plan_path"])
    if sha256(central_path) != manifest["central_plan_sha256"]:
        raise RuntimeError("central plan differs from the frozen bytes")
    central = json.loads(central_path.read_text())
    entries = {
        entry["slot"]: entry
        for entry in central["entries"]
        if entry["host"] == "snowball-mac"
    }
    plan = manifest["algotune_plan"]
    if len(entries) != len(plan):
        raise RuntimeError("Mac plan length differs from the central plan")
    by_key = {binding["task_key"]: task_id for task_id, binding in tasks.items()}
    if [item["seq"] for item in plan] != list(range(1, len(plan) + 1)):
        raise RuntimeError("Mac execution seq must preserve the preregistered 1-15 order")
    for actual in plan:
        expected = entries.get(actual.get("central_slot"))
        if expected is None:
            raise RuntimeError(f"unknown central slot for Mac seq {actual['seq']}")
        if {
            "central_slot": expected["slot"],
            "task_id": by_key[expected["task_key"]],
            "repeat": expected["repeat"],
            "mode": expected["mode"],
        } != {key: actual[key] for key in ("central_slot", "task_id", "repeat", "mode")}:
            raise RuntimeError(f"Mac seq {actual['seq']} differs from the central plan")
        if expected.get("dev_cases") != 5 or expected.get("final_cases") != 15:
            raise RuntimeError(f"central slot {expected['slot']} has unexpected case counts")
    if {item["central_slot"] for item in plan} != set(entries):
        raise RuntimeError("Mac plan does not bind every central slot exactly once")
    validate_plan(plan, list(tasks))
    pending = sorted(
        entry["slot"] for entry in entries.values() if entry.get("binding_status") != "ready"
    )
    return [f"central plan bindings are not ready: {pending}"] if pending else []


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
        selection = task.manifest.get("selection", {})
        if selection.get("dev_cases") != 5 or selection.get("final_cases") != 15:
            raise RuntimeError(f"task does not contain the frozen 5/15 split: {task_id}")
        if task.adapter.environment_info(task, measure) != binding["environment"]:
            raise RuntimeError(f"container environment differs from freeze: {task_id}")
        check_image(binding["environment"])
        check_image(binding["environment"]["judge"])
        for mode, expected in binding["prompt_sha256"].items():
            actual = hashlib.sha256(prompt.system_prompt(task, mode).encode()).hexdigest()
            if actual != expected:
                raise RuntimeError(f"system prompt differs from freeze: {task_id}/{mode}")
        loaded[task_id] = task
    return loaded


def check_calibration(manifest: dict) -> list[str]:
    calibration = manifest["calibration"]
    if not calibration["accepted"]:
        return ["timing-v2 calibration is not accepted"]
    evidence = check_tracked(repository_root() / calibration["evidence_path"])
    if sha256(evidence) != calibration["evidence_sha256"]:
        raise RuntimeError("accepted calibration evidence differs from freeze")
    summary = json.loads(evidence.read_text())
    expected_header = {
        "schema": "routeevo-algotune-calibration-freeze-v1",
        "status": "accepted",
        "code_sha": manifest["code_sha"],
        "measure": manifest["measure"],
        "model_requests": 0,
        "final_evaluations": 0,
    }
    if any(summary.get(key) != value for key, value in expected_header.items()):
        raise RuntimeError("calibration acceptance header differs from the freeze")
    if set(summary.get("tasks", {})) != set(manifest["tasks"]):
        raise RuntimeError("calibration task set differs from the freeze")
    for task_id, binding in manifest["tasks"].items():
        row = summary["tasks"][task_id]
        expected = {
            "status": "accepted",
            "manifest_sha256": binding["manifest_sha256"],
            "environment": binding["environment"],
            "warmups": manifest["measure"]["function_warmups"],
            "timings": manifest["measure"]["repeats"],
            "rounds": 3,
            "strict_false_improvements": 0,
            "positive_control_passed": True,
            "negative_control_passed": True,
        }
        if any(row.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"calibration acceptance differs for task: {task_id}")
        raw = check_tracked(repository_root() / row["evidence_path"])
        if sha256(raw) != row["evidence_sha256"]:
            raise RuntimeError(f"raw calibration evidence differs for task: {task_id}")
    return []


def preflight(args, manifest: dict, *, require_ready: bool) -> tuple[dict, dict]:
    if not args.root.is_absolute() or not args.out.is_absolute():
        raise RuntimeError("--root and --out must be absolute paths")
    check_source(args, manifest)
    if platform.python_version() != manifest["python_version"]:
        raise RuntimeError("Python version differs from the freeze")
    if subprocess.check_output(["uv", "--version"], text=True).strip() != manifest["uv_version"]:
        raise RuntimeError("uv version differs from the freeze")
    blockers = check_model(manifest)
    tasks = check_tasks(args, manifest)
    blockers.extend(check_plan(manifest, manifest["tasks"]))
    if docker_runtime() != manifest["docker_runtime"]:
        raise RuntimeError("Docker VM resources differ from the frozen runtime")
    if manifest["freeze_status"] != "ready":
        blockers.append(f"freeze status is {manifest['freeze_status']}")
    blockers.extend(check_calibration(manifest))
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
        "manifest_sha256": sha256(args.manifest),
        "tasks": list(tasks),
        "slots": len(manifest["algotune_plan"]),
        "model_calls": 0,
        "final_evaluations": 0,
        "blockers": blockers,
    }
    if require_ready and blockers:
        raise RuntimeError("formal execution blocked: " + "; ".join(blockers))
    return tasks, result


def check_worker_authorization(args, manifest: dict) -> None:
    token = os.environ.get("ROUTEEVO_FORMAL_BATCH_TOKEN")
    authorization_path = args.out / "batch-authorization.json"
    if not token or not authorization_path.exists():
        raise RuntimeError("worker is not authorized by the formal batch controller")
    authorization = json.loads(authorization_path.read_text())
    expected = {
        "plan_id": manifest["plan_id"],
        "manifest_sha256": sha256(args.manifest),
        "authorized_seq": args.seq,
        "token_sha256": sha256_text(token),
    }
    if authorization != expected:
        raise RuntimeError("worker authorization does not match this frozen slot")
    frozen_manifest = args.out / "frozen-manifest.json"
    if not frozen_manifest.exists() or sha256(frozen_manifest) != sha256(args.manifest):
        raise RuntimeError("batch freeze manifest is missing or changed")


def worker(args, manifest: dict) -> None:
    from routeevo import config, research_compare

    if not args.execute or args.seq is None:
        raise RuntimeError("the internal worker requires --execute and --seq")
    check_worker_authorization(args, manifest)
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
        label=(
            f"AlgoTune formal seq {args.seq} / central slot {step['central_slot']}"
        ),
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
        "manifest_sha256": sha256(EXPECTED_MANIFEST),
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
        frozen_manifest = args.out / "frozen-manifest.json"
        if sha256(frozen_manifest) != sha256(args.manifest):
            raise RuntimeError("recorded freeze manifest differs from the current bytes")
        if (
            out.get("plan") != manifest["algotune_plan"]
            or out.get("code_sha") != manifest["code_sha"]
            or out.get("manifest_sha256") != sha256(args.manifest)
        ):
            raise RuntimeError("existing aggregate differs from the frozen execution")
        out["status"] = "running"
        out.pop("ended_at", None)
    else:
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "frozen-manifest.json").write_bytes(args.manifest.read_bytes())
        out = initial_result(manifest)

    script = str(Path(__file__).resolve())
    started = time.monotonic()
    batch_token = secrets.token_hex(32)
    authorization_path = args.out / "batch-authorization.json"

    def save() -> None:
        research_compare.summarize(out)
        out.pop("cost", None)
        out["cost"] = comparison_summary(out)["cost"]
        write(aggregate_path, out)

    def checked_result(saved: dict, step: dict, source: Path) -> dict:
        if (
            saved.get("plan_id") != manifest["plan_id"]
            or saved.get("protocol") != manifest["protocol"]
            or saved.get("plan") != [step]
            or saved.get("measure") != manifest["measure"]
            or saved.get("limits") != manifest["limits"]
            or saved.get("fixed_model") != "small"
            or saved.get("final_evaluation") is not True
            or saved.get("dev_only") is not False
            or saved.get("price_snapshot") != manifest["pricing"]
            or len(saved.get("runs", [])) != 1
        ):
            raise RuntimeError(f"slot evidence identity mismatch: {source}")
        row = saved["runs"][0]
        identity = ("seq", "central_slot", "task_id", "repeat", "mode")
        if {key: row.get(key) for key in identity} != {key: step[key] for key in identity}:
            raise RuntimeError(f"slot run identity mismatch: {source}")
        return row

    def checked_slot(path: Path, step: dict) -> dict:
        return checked_result(json.loads(path.read_text()), step, path)

    def launch(step: dict) -> dict:
        slot = args.out / "slots" / f"{step['seq']:02d}.json"
        if slot.exists():
            return checked_slot(slot, step)
        attempt_id = secrets.token_hex(4)
        logfile = args.out / "logs" / f"{step['seq']:02d}-{attempt_id}.log"
        logfile.parent.mkdir(parents=True, exist_ok=True)
        existing_comparisons = {path.resolve() for path in (args.root / "comparisons").glob("research-*.json")}
        attempt_started = time.time()
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
        authorization = {
            "plan_id": manifest["plan_id"],
            "manifest_sha256": sha256(args.manifest),
            "authorized_seq": step["seq"],
            "token_sha256": sha256_text(batch_token),
        }
        write(authorization_path, authorization)
        worker_environment = {**os.environ, "ROUTEEVO_FORMAL_BATCH_TOKEN": batch_token}
        try:
            with logfile.open("x") as log:
                process = subprocess.run(
                    command,
                    env=worker_environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
        finally:
            write(authorization_path, {**authorization, "authorized_seq": None})
        if not process.returncode and slot.exists():
            return checked_slot(slot, step)
        comparisons = sorted(
            (args.root / "comparisons").glob("research-*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in comparisons:
            if path.resolve() in existing_comparisons or path.stat().st_mtime < attempt_started:
                continue
            partial = json.loads(path.read_text())
            if partial.get("plan_id") != manifest["plan_id"]:
                continue
            try:
                row = checked_result(partial, step, path)
            except RuntimeError:
                continue
            row["recorded_status"] = row.get("status")
            row.update(
                status="interrupted",
                error=f"worker exited {process.returncode}; inspect {logfile}",
            )
            partial.update(status="interrupted", runs=[row])
            write(slot, partial)
            return row
        return {
            **step,
            "_launch_error": f"worker exited {process.returncode}; inspect {logfile}",
        }

    if args.resume:
        for step in manifest["algotune_plan"]:
            index = next(i for i, row in enumerate(out["runs"]) if row["seq"] == step["seq"])
            aggregate_row = out["runs"][index]
            slot = args.out / "slots" / f"{step['seq']:02d}.json"
            if aggregate_row.get("status") == "not_run":
                if slot.exists():
                    out["runs"][index] = checked_slot(slot, step)
                continue
            if not slot.exists():
                raise RuntimeError(f"recorded aggregate row has no slot evidence: {step['seq']}")
            if checked_slot(slot, step) != aggregate_row:
                raise RuntimeError(f"aggregate and slot evidence differ: {step['seq']}")

    save()
    try:
        if out["fair"] is False:
            raise RuntimeError("cannot resume a comparison with mixed frozen configurations")
        for step in manifest["algotune_plan"]:
            existing = next(row for row in out["runs"] if row["seq"] == step["seq"])
            if existing.get("status") != "not_run":
                continue
            slot_start = time.monotonic()
            result = launch(step)
            if result.get("_launch_error"):
                out.setdefault("launch_errors", []).append(
                    {
                        "seq": step["seq"],
                        "at": datetime.now(timezone.utc).isoformat(),
                        "error": result["_launch_error"],
                    }
                )
                out["status"] = "interrupted"
                save()
                break
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
            if out["fair"] is False:
                out["status"] = "interrupted"
                break
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
            final_status = (result.get("final_evaluation") or {}).get("status")
            if (
                result.get("error")
                or result.get("stop_reason") in FATAL_STOP_REASONS
                or final_status in FATAL_FINAL_STATUSES
                or (
                    result.get("final_status") == "failed"
                    and result.get("final_evaluation") is None
                )
            ):
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
        if arguments.resume:
            parser.error("the internal worker does not accept --resume")
        worker(arguments, frozen)
    else:
        if arguments.seq is not None:
            parser.error("--seq is only valid for the internal worker")
        main(arguments, frozen)
