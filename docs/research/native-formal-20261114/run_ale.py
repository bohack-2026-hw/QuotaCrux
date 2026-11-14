"""Run the frozen ALE wave plan using two isolated, existing research executors."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def check(args, manifest):
    from quotacrux import config, db, taskpkg
    from quotacrux.agent import actions, prompt
    from quotacrux.research_compare import validate_plan

    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if actual != manifest["code_sha"] or subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("source checkout differs from frozen clean SHA")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != manifest["executor_sha256"]:
        raise RuntimeError("wave executor differs from frozen bytes")
    models = config.default_model_configs()
    if models["small"].public_dict() != manifest["model"]:
        raise RuntimeError("model configuration differs from frozen manifest")
    schema_sha = hashlib.sha256(json.dumps(actions.ACTION_SCHEMA, sort_keys=True).encode()).hexdigest()
    if schema_sha != manifest["action_schema_sha256"] or prompt.PROMPT_VERSION != manifest["prompt_version"]:
        raise RuntimeError("prompt/schema version differs from freeze")
    binding = manifest["workers"][args.worker]
    if config.VAR_DIR != args.root / f"var-worker-{args.worker}":
        raise RuntimeError("worker VAR_DIR is not the registered isolated directory")
    task = taskpkg.load(binding["task_id"])
    row = db.one("SELECT manifest_sha256 FROM tasks WHERE task_id=?", (task.task_id,))
    if row["manifest_sha256"] != binding["manifest_sha256"]:
        raise RuntimeError("task manifest differs from freeze")
    measure = config.MeasureConfig(**binding["measure"])
    if task.adapter.environment_info(task, measure) != binding["environment"]:
        raise RuntimeError("candidate/judge image or execution environment changed")
    selected = [s for s in manifest["ale_plan"] if s["worker"] == args.worker]
    validate_plan(selected, [task.task_id])
    for mode, expected in binding["prompt_sha256"].items():
        if hashlib.sha256(prompt.system_prompt(task, mode).encode()).hexdigest() != expected:
            raise RuntimeError("system prompt differs from freeze")
    return task, measure


def worker(args, manifest):
    from quotacrux import config, research_compare
    task, measure = check(args, manifest)
    if not args.execute:
        print(json.dumps({"worker": args.worker, "task_id": task.task_id, "status": "ready"}), flush=True)
        return
    step = next(s for s in manifest["ale_plan"] if s["seq"] == args.seq and s["worker"] == args.worker)
    output = args.out / "slots" / f"{args.seq:02d}.json"
    if output.exists():
        raise RuntimeError("slot already has evidence; do not replace or silently rerun")
    result = research_compare.execute([task.task_id], limits=config.RunLimits(**manifest["limits"]),
        fixed_model="small", final_evaluation=True, measure=measure, plan=[step],
        plan_id=manifest["plan_id"], pricing=manifest["pricing"], label=f"ALE formal slot {args.seq}")
    write(output, result)
    print(json.dumps({"seq": args.seq, "run_id": result["runs"][0].get("run_id"), "status": result["status"]}), flush=True)


def main(args, manifest):
    from quotacrux import research_compare
    from quotacrux.research_views import comparison_summary
    script = str(Path(__file__).resolve())

    def command(name, execute=False, seq=None):
        cmd = [sys.executable, script, "--root", str(args.root), "--manifest", str(args.manifest),
               "--out", str(args.out), "--worker", name]
        if execute:
            cmd += ["--execute", "--seq", str(seq)]
        return cmd

    def environment(name):
        return {**os.environ, "ROUTEEVO_VAR_DIR": str(args.root / f"var-worker-{name}")}

    for name in manifest["workers"]:
        subprocess.run(command(name), env=environment(name), check=True)
    if not args.execute:
        return
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / "frozen-manifest.json", manifest)
    out = {"comparison_id": manifest["plan_id"], "plan_id": manifest["plan_id"],
           "protocol": manifest["protocol"], "label": "ALE formal 15-slot feedback comparison",
           "code_sha": manifest["code_sha"], "status": "running", "fair": None,
           "created_at": datetime.now(timezone.utc).isoformat(), "final_evaluation": True,
           "price_snapshot": manifest["pricing"], "limits": manifest["limits"],
           "plan": manifest["ale_plan"], "runs": [dict(s, status="not_run", final_status="not_run") for s in manifest["ale_plan"]],
           "waves": []}
    started = time.monotonic()

    def save():
        research_compare.summarize(out)
        out.pop("cost", None)
        out["cost"] = comparison_summary(out)["cost"]
        write(args.out / f"{manifest['plan_id']}.json", out)

    def launch(step):
        logfile = args.out / "logs" / f"{step['seq']:02d}.log"
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open("x") as log:
            process = subprocess.run(command(step["worker"], True, step["seq"]),
                env=environment(step["worker"]), stdout=log, stderr=subprocess.STDOUT)
        output = args.out / "slots" / f"{step['seq']:02d}.json"
        if process.returncode or not output.exists():
            # execute() retains its comparison even if its caller exits before copying the slot.
            for path in (args.root / f"var-worker-{step['worker']}" / "comparisons").glob("research-*.json"):
                partial = json.loads(path.read_text())
                if partial.get("plan_id") == manifest["plan_id"]:
                    row = next((r for r in partial["runs"] if r["seq"] == step["seq"]), None)
                    if row is not None:
                        write(output, partial)
                        return dict(row, status="interrupted", error=f"worker exited {process.returncode}; inspect {logfile}")
            return dict(step, status="interrupted", final_status="not_run",
                        error=f"worker exited {process.returncode}; inspect {logfile}")
        return json.loads(output.read_text())["runs"][0]

    save()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for wave in sorted({s["wave"] for s in manifest["ale_plan"]}):
                steps = [s for s in manifest["ale_plan"] if s["wave"] == wave]
                wave_start = time.monotonic()
                futures = [pool.submit(launch, step) for step in steps]
                results = [f.result() for f in futures]
                for result in results:
                    index = next(i for i, s in enumerate(out["runs"]) if s["seq"] == result["seq"])
                    out["runs"][index] = result
                out["waves"].append({"wave": wave, "wall_clock_s": time.monotonic()-wave_start,
                                     "slots": [s["seq"] for s in steps]})
                save()
                print(json.dumps({"wave": wave, "finished": sum("run_id" in s for s in out["runs"]),
                                  "statuses": [r["status"] for r in results], "elapsed_s": time.monotonic()-started}), flush=True)
                if any(r.get("error") or r.get("stop_reason") in ("environment_error", "internal_error", "model_api_error", "user_stopped") for r in results):
                    out["status"] = "interrupted"
                    break
            else:
                out["status"] = "completed" if all(s.get("final_status") == "completed" and s["status"] == "completed" for s in out["runs"]) else "failed"
    except BaseException:
        out["status"] = "interrupted"
        raise
    finally:
        out["ended_at"] = datetime.now(timezone.utc).isoformat()
        out["batch_wall_clock_s"] = time.monotonic()-started
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--worker", choices=("a", "b"))
    parser.add_argument("--seq", type=int)
    arguments = parser.parse_args()
    frozen = json.loads(arguments.manifest.read_text())
    (worker if arguments.worker else main)(arguments, frozen)
