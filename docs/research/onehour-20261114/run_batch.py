"""Four predeclared generation/routing policies on one host; no automatic retries."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "repo", "env-file", "task-source", "previous-freeze"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--host", choices=("laptop", "desktop"), required=True)
    p.add_argument("--cpu", required=True)
    p.add_argument("--judge-image", help="host-local ID of the imported judge image")
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["ROUTEEVO_VAR_DIR"] = str(root / "var")
    sys.path.insert(0, str(args.repo.resolve() / "backend/src"))
    from routeevo import config, db, taskpkg
    from routeevo.agent import actions, prompt, routing
    from routeevo.agent.runner import Runner, RunOptions
    from routeevo.routing_ablation import costs

    config.load_dotenv(args.env_file)
    os.environ["ROUTEEVO_NO_DOTENV"] = "1"
    frozen = json.loads(args.previous_freeze.read_text())
    # The previous batch supplies public model settings and price provenance only.
    small, large = frozen["models"]["small"], frozen["models"]["large"]
    values = {"QWEN_BASE_URL": small["base_url"], "QWEN_MODEL": small["model"],
              "QWEN_RESPONSE_FORMAT": small["response_format"],
              "QWEN_MAX_OUTPUT_TOKENS": str(small["max_output_tokens"]),
              "QWEN_ENABLE_THINKING": "false", "QWEN_REASONING_EFFORT": "",
              "OPENAI_BASE_URL": large["base_url"], "OPENAI_MODEL": large["model"],
              "OPENAI_REASONING_EFFORT": large["reasoning_effort"],
              "OPENAI_MAX_OUTPUT_TOKENS": str(large["max_output_tokens"])}
    os.environ.update(values)
    os.environ.pop("QWEN_TEMPERATURE", None)
    assert os.environ.get("QWEN_API_KEY") and os.environ.get("OPENAI_API_KEY"), "model credentials missing"
    assert sys.version_info[:2] == (3, 12), "Python 3.12 required"
    assert config.VAR_DIR == root / "var", "isolated ledger path differs"
    models = {k: v.public_dict() for k, v in config.default_model_configs().items()}
    models["decisions"] = routing.decision_config("router_action").public_dict()
    assert models == frozen["models"], "model settings differ"

    source_task_id = next(iter(frozen["tasks"]))
    manifest = json.loads((args.task_source / "manifest.json").read_text())
    source_manifest_sha = digest(json.dumps(manifest, sort_keys=True).encode())
    assert source_manifest_sha == frozen["tasks"][source_task_id]["manifest_sha256"], "source task manifest differs"
    task_id = source_task_id + "-onehour-" + args.host
    manifest["task_id"] = task_id
    if args.judge_image:
        manifest["native"]["image_id"] = args.judge_image
    manifest_sha = digest(json.dumps(manifest, sort_keys=True).encode())
    if not db.one("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)):
        dest = config.TASK_DATA_DIR / task_id
        shutil.copytree(args.task_source, dest)
        (dest / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
        db.insert("tasks", {"task_id": task_id, "family": manifest["family"], "split": manifest["split"],
            "manifest_json": db.dumps(manifest), "manifest_sha256": manifest_sha, "registered_at": db.now()})
    task = taskpkg.load(task_id, verify=True)
    assert db.one("SELECT COUNT(*) AS n FROM snapshot_items WHERE snapshot_id='v0'")["n"] == 0
    measure = config.MeasureConfig(**{**frozen["tasks"][source_task_id]["measure"], "cpuset_cpus": args.cpu})
    limits = config.RunLimits(**frozen["limits"])
    assert (limits.wall_clock_s, limits.max_model_requests, limits.max_candidates) == (360, 20, 10)
    env = task.adapter.environment_info(task, measure)
    judge_id = subprocess.check_output(["docker", "image", "inspect", manifest["native"]["image_id"],
                                       "--format", "{{.Id}}"], text=True).strip()
    assert judge_id == manifest["native"]["image_id"]
    source_files = {}
    backend = args.repo / "backend"
    for path in sorted((backend / "src").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            source_files[str(path.relative_to(backend))] = digest(path.read_bytes())
    source_files["uv.lock"] = digest((backend / "uv.lock").read_bytes())
    order = ["fixed_small", "fixed_large", "adaptive_rule", "action_decisions"]
    if args.host == "laptop":
        order.reverse()
    record = {"study": "onehour-policy-comparison", "host": args.host, "hostname": socket.gethostname(),
        "source_commit": frozen["experiment_sha"], "source_files": source_files,
        "runner_sha256": digest(Path(__file__).read_bytes()), "task_id": task_id,
        "task_manifest_sha256": manifest_sha, "source_task_manifest_sha256": source_manifest_sha,
        "task_package_files": manifest["files"], "models": models, "limits": limits.to_dict(),
        "measure": measure.to_dict(), "environment": env, "python": platform.python_version(),
        "cpu": subprocess.check_output(["lscpu", "-J"], text=True), "loadavg": os.getloadavg(),
        "snapshot": "v0", "research_mode": "feedback", "final_evaluation": True,
        "prompt_sha256": digest(prompt.system_prompt(task, "feedback").encode()),
        "action_schema_sha256": digest(json.dumps(actions.ACTION_SCHEMA, sort_keys=True).encode()),
        "price_snapshots": frozen["price_snapshots"], "plan": order}
    assert record["prompt_sha256"] == frozen["prompt_hashes_by_task"][source_task_id]
    assert record["action_schema_sha256"] == frozen["action_schema_sha256"]
    preflight = root / "preflight.json"
    if not args.execute:
        # Baseline-only dev calibration does not make model requests or expose final scores.
        ev = task.adapter.evaluate(task, task.initial_code.encode(), "dev", measure, limits)
        assert ev.status == "passed" and ev.detail["objective"]["value"] == 44120, "c0 dev calibration failed"
        record["dev_calibration"] = {"status": ev.status, "objective": ev.detail["objective"]}
        record["checked_at"] = db.now()
        save(preflight, record)
        print(json.dumps({"host": args.host, "status": "checked", "root": str(root),
                          "c0_dev": 44120, "source_files_sha256": digest(json.dumps(source_files, sort_keys=True).encode())}), flush=True)
        return
    checked = json.loads(preflight.read_text())
    for key in ("source_files", "runner_sha256", "task_manifest_sha256", "models", "limits", "measure",
                "environment", "snapshot", "prompt_sha256", "action_schema_sha256", "price_snapshots", "plan"):
        assert record[key] == checked[key], f"preflight drift: {key}"
    assert db.one("SELECT COUNT(*) AS n FROM runs")["n"] == 0, "batch already contains runs"
    with (root / "execution-freeze.json").open("x") as out:
        json.dump(checked, out, ensure_ascii=False, indent=2)
    batch = {"host": args.host, "status": "running", "created_at": db.now(), "runs": [
        {"seq": i + 1, "variant": variant, "status": "not_run"} for i, variant in enumerate(order)]}
    save(root / "batch.json", batch)
    start = time.monotonic()
    try:
        for step in batch["runs"]:
            if time.monotonic() - start > 2400:
                batch["status"] = "time_limit"
                break
            variant = step["variant"]
            fixed = {"fixed_small": "small", "fixed_large": "large"}.get(variant)
            opts = RunOptions(task_id=task_id, mode="eval", snapshot_id="v0", research_mode="feedback",
                research_model_policy="fixed" if fixed else "adaptive", fixed_model=fixed, router=False,
                routing=config.RoutingConfig("decisions" if variant == "action_decisions" else "llm", "rule"),
                final_evaluation=True, limits=limits, measure=measure,
                label=f"onehour-20261114 {args.host} {variant}")
            runner = Runner(opts)
            step.update(run_id=runner.create(), status="running", started_at=db.now())
            save(root / "batch.json", batch)
            print(json.dumps(step), flush=True)
            rep = runner.execute()
            step.update(status=rep["status"], stop_reason=rep["stop_reason"], final_status=rep["outcome"]["final_status"],
                report_path=str(runner.dir / "report.json"), timing=rep["timing"],
                cost=costs(rep["usage"]["by_model"], frozen["price_snapshots"]))
            save(root / "batch.json", batch)
            print(json.dumps({k: step[k] for k in ("seq", "variant", "run_id", "status", "final_status")}), flush=True)
            if rep["status"] != "completed" or rep["outcome"]["final_status"] != "completed":
                batch["status"] = "interrupted"
                break
        else:
            batch["status"] = "completed"
    except BaseException as exc:
        batch.update(status="interrupted", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        batch.update(ended_at=db.now(), elapsed_s=time.monotonic() - start)
        save(root / "batch.json", batch)


if __name__ == "__main__":
    main()
