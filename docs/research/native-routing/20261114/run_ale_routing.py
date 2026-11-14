"""Check the frozen desktop routing study; --execute runs its 12 serial episodes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path("/home/hycx233/routeevo-routing-formal-20261114")
ALE_SEQUENCES = [1, 2, 3, 4, 9, 10, 11, 12, 17, 18, 19, 20]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, label):
    require(isinstance(value, dict), f"{label} must be an object")
    missing = set(names) - value.keys()
    require(not missing, f"{label} missing fields: {', '.join(sorted(missing))}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def check(args):
    root = args.root.resolve()
    repo = root / "repo"
    raw = args.freeze.read_bytes()
    frozen = json.loads(raw)
    fields(frozen, ("status", "study", "plan_id", "experiment_sha", "executor_sha256", "uv_lock_sha256",
                    "mode", "research_mode", "research_model_policy", "snapshot_id", "fixed_model",
                    "initial_memory_router", "final_evaluation", "limits", "models", "tasks", "plan",
                    "prompt_hashes_by_task", "prompt_version", "action_schema_sha256", "routing_manifest",
                    "price_snapshots"), "freeze")
    expected = {"status": "frozen_ale", "study": "routing", "mode": "eval", "research_mode": "feedback",
                "research_model_policy": "adaptive", "snapshot_id": "v0", "fixed_model": None,
                "initial_memory_router": False, "final_evaluation": True}
    for key, value in expected.items():
        require(frozen[key] == value and type(frozen[key]) is type(value), f"freeze {key} differs from this study")
    require(command("git", "-C", str(repo), "status", "--porcelain") == "", "execution checkout is not clean")
    require(command("git", "-C", str(repo), "rev-parse", "HEAD") == frozen["experiment_sha"], "experiment SHA differs")
    require(sha(Path(__file__).read_bytes()) == frozen["executor_sha256"], "executor SHA256 differs")
    require(sha((repo / "backend/uv.lock").read_bytes()) == frozen["uv_lock_sha256"], "uv.lock SHA256 differs")
    require(sys.version_info[:2] == (3, 12), "execution requires Python 3.12")
    var = root / "var"
    require(os.environ.get("ROUTEEVO_VAR_DIR", str(var)) == str(var), "ROUTEEVO_VAR_DIR differs from root/var")
    os.environ["ROUTEEVO_VAR_DIR"] = str(var)
    sys.path.insert(0, str(repo / "backend/src"))
    from routeevo import config, db, routing_ablation, taskpkg
    from routeevo.agent import actions, prompt, routing
    from routeevo.research_views import validate_pricing
    from routeevo.sandbox import executor

    require(config.BACKEND_DIR.resolve() == repo / "backend", "imported backend differs from execution checkout")
    fields(frozen["limits"], config.RunLimits.__dataclass_fields__, "limits")
    limits = config.RunLimits(**frozen["limits"])
    require((limits.wall_clock_s, limits.max_model_requests, limits.max_candidates) == (900, 20, 10),
            "routing budget must be 900 seconds / 20 total HTTP requests / 10 candidates")
    models = {key: value.public_dict() for key, value in config.default_model_configs().items()}
    models["decisions"] = routing.decision_config("router_action").public_dict()
    require(models == frozen["models"], "public small/large/decisions configuration differs")
    require(os.environ["ROUTEEVO_VAR_DIR"] == str(var), "dotenv changed the execution VAR_DIR")
    require(prompt.PROMPT_VERSION == frozen["prompt_version"], "prompt version differs")
    require(sha(json.dumps(actions.ACTION_SCHEMA, sort_keys=True).encode()) == frozen["action_schema_sha256"],
            "action schema SHA256 differs")
    manifests = {name: routing.manifest(cfg) for name, cfg in routing_ablation.VARIANTS.items()}
    require(manifests == frozen["routing_manifest"], "routing manifests differ")
    prices = json.loads((args.prices or root / "prices.json").read_bytes())
    require(prices == frozen["price_snapshots"] and set(prices) == {"small", "large", "decisions"},
            "price snapshots differ or model roles are missing")
    for role, price in prices.items():
        validate_pricing(price)
        require(price["model"] == models[role]["model"], f"price model differs for {role}")

    plan = json.loads((args.plan or root / "ale-plan.json").read_bytes())
    require(isinstance(plan, list) and len(plan) == 12, "ALE plan must contain 12 slots")
    task_ids = list(dict.fromkeys(row["task_id"] for row in plan))
    require(len(task_ids) == 1, "ALE routing study requires exactly one task")
    task_id = task_ids[0]
    routing_ablation.validate_plan(plan, task_ids)
    require(plan == [row for row in frozen["plan"] if row["task_id"] == task_id], "ALE plan differs from frozen order")
    require([row["seq"] for row in plan] == ALE_SEQUENCES, "original ALE sequence numbers changed")
    expected_order = routing_ablation.make_plan(task_ids, 3)
    require(all(row["mode"] == "feedback" and (row["repeat"], row["variant"], row["routing"]) ==
                (expected["repeat"], expected["variant"], expected["routing"])
                for row, expected in zip(plan, expected_order)), "ALE repeat/variant rotation changed")
    fields(frozen["tasks"], [task_id], "tasks")
    binding = frozen["tasks"][task_id]
    fields(binding, ("accepted_for_freeze", "host", "problem", "manifest_sha256", "package_hashes", "source",
                     "selection", "objective", "environment", "measure", "concurrency", "api_in_flight_limit",
                     "planned_root", "dev_cases", "final_cases"), "ALE binding")
    require(binding["accepted_for_freeze"] is True, "ALE task binding is not accepted for freeze")
    require(binding["host"] == "desktop" and binding["problem"] == "ahc026", "task binding is not desktop ahc026")
    require(Path(binding["planned_root"]).resolve() == root, "execution root differs from frozen desktop root")
    require(binding["concurrency"] == binding["api_in_flight_limit"] == 1, "ALE routing execution must be serial")
    fields(binding["measure"], config.MeasureConfig.__dataclass_fields__, "measure")
    measure = config.MeasureConfig(**binding["measure"])
    require(measure.cpuset_cpus == "4" and measure.cpus == 1, "candidate CPU must be fixed to CPU 4 / one CPU")

    require(config.DB_PATH.is_file(), "registered SQLite ledger is missing")
    conn = sqlite3.connect(config.DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    previous = getattr(db._local, "conn", None)
    db._local.conn = conn  # taskpkg.load must not initialize or migrate the ledger in check mode.
    try:
        task = taskpkg.load(task_id, verify=True)
        registered = db.one("SELECT manifest_sha256 FROM tasks WHERE task_id=?", (task_id,))["manifest_sha256"]
        require(registered == sha(json.dumps(task.manifest, sort_keys=True).encode()) == binding["manifest_sha256"],
                "registered task manifest SHA256 differs")
        counts = {name: db.one(f"SELECT COUNT(*) AS n FROM {name}")["n"] for name in ("runs", "model_calls")}
        require(db.one("SELECT 1 FROM snapshots WHERE snapshot_id='v0' AND version=0") is not None and
                db.one("SELECT COUNT(*) AS n FROM snapshot_items WHERE snapshot_id='v0'")["n"] == 0,
                "v0 snapshot is missing or contains experience")
    finally:
        db._local.conn = previous
        conn.close()
    require(task.family == "ale-bench" and task.manifest["problem"]["key"] == "ahc026", "registered task is not ALE ahc026")
    for actual, key in ((task.manifest["files"], "package_hashes"), (task.manifest["source"], "source"),
                        (task.manifest["selection"], "selection"), (task.objective, "objective")):
        require(actual == binding[key], f"task {key} differs")
    require(task.manifest["dev_params"]["cases"] == binding["dev_cases"] == 5 and
            task.manifest["final_params"]["cases"] == binding["final_cases"] == 15, "task split must be 5 dev / 15 final")
    require(sha(prompt.system_prompt(task, "feedback").encode()) == frozen["prompt_hashes_by_task"][task_id],
            "task system prompt SHA256 differs")

    tag = executor.image_tag()
    candidate_id = command("docker", "image", "inspect", tag, "--format", "{{.Id}}")
    judge = {key: task.manifest["native"][key] for key in ("image_tag", "image_id")}
    require(command("docker", "image", "inspect", judge["image_id"], "--format", "{{.Id}}") == judge["image_id"],
            "judge image is missing or changed")
    environment = {"image_tag": tag, "image_id": candidate_id,
        "docker_server": command("docker", "version", "--format", "{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}"),
        "container_python": "3.12-slim (pinned digest in Dockerfile)",
        "limits": {"cpus": measure.cpus, "cpuset_cpus": measure.cpuset_cpus, "memory": measure.memory,
                   "pids_limit": measure.pids_limit, "network": "none", "read_only_rootfs": True, "user": "65534:65534"},
        "judge": judge}
    require(environment == binding["environment"], "actual candidate/judge environment differs")
    prior_comparisons = list((var / "comparisons").glob("research-routing-*.json"))
    info = {"status": "checked", "checked_at": datetime.now(timezone.utc).isoformat(), "plan_id": frozen["plan_id"],
            "experiment_sha": frozen["experiment_sha"], "executor_sha256": frozen["executor_sha256"],
            "freeze_sha256": sha(raw), "task_id": task_id, "manifest_sha256": registered, "slots": len(plan),
            "root": str(root), "candidate_cpu": measure.cpuset_cpus, "existing_counts": counts,
            "existing_routing_comparisons": len(prior_comparisons)}
    if args.execute:
        require(not any(counts.values()) and not prior_comparisons, "paid records already exist; automatic replacement/resume is forbidden")
        # Exclusive creation also rejects a second launcher before its first run is registered.
        with (root / "execution-freeze.json").open("xb") as output:
            output.write(raw)
        print(json.dumps(info), flush=True)
        result = routing_ablation.execute(task_ids, "v0", repeats=3, limits=limits, measure=measure,
            research_mode="feedback", research_model_policy="adaptive", final_evaluation=True,
            plan=plan, plan_id=frozen["plan_id"], pricing=prices, label="Frozen desktop ahc026 routing study")
        print(json.dumps({"comparison_id": result["comparison_id"], "status": result["status"],
                          "fair": result["fair"], "artifact": result["path"]}), flush=True)
        return 0 if result["status"] == "completed" else 1
    print(json.dumps(info), flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--plan", type=Path, help="defaults to ROOT/ale-plan.json")
    parser.add_argument("--prices", type=Path, help="defaults to ROOT/prices.json")
    parser.add_argument("--execute", action="store_true", help="run paid episodes after all frozen checks pass")
    args = parser.parse_args()
    try:
        sys.exit(check(args))
    except Exception as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")
