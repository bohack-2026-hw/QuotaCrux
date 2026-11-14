"""Four routing variants on one frozen snapshot; only routing configuration may differ."""

from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
import uuid

from . import compare, config, db, report
from .agent.runner import RunOptions, Runner

VARIANTS = {
    "baseline": config.RoutingConfig("llm", "rule"),
    "action_decisions": config.RoutingConfig("decisions", "rule"),
    "model_decisions": config.RoutingConfig("llm", "decisions"),
    "both_decisions": config.RoutingConfig("decisions", "decisions"),
}


def plan(task_ids: list[str], repeats: int) -> list[dict]:
    if repeats < 1 or not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("provide unique tasks and at least one repeat")
    variants = list(VARIANTS)
    out = []
    for repeat in range(repeats):
        for i, task_id in enumerate(task_ids):
            offset = (repeat + i) % len(variants)
            for variant in variants[offset:] + variants[:offset]:
                out.append({"seq": len(out) + 1, "task_id": task_id, "repeat": repeat + 1,
                            "variant": variant, "routing": VARIANTS[variant].to_dict()})
    return out


def summarize(data: dict) -> dict:
    reports = {r["run_id"]: report.build(r["run_id"]) for r in data["runs"] if r.get("run_id")}
    hashes, per_task, routing_matches = set(), {}, True
    for row in data["runs"]:
        if not row.get("run_id"):
            continue
        rep = reports[row["run_id"]]
        cfg = dict(rep["config"])
        actual = cfg.pop("routing")
        routing_matches &= all(actual[key] == value for key, value in row["routing"].items())
        routing_matches &= rep["snapshot_id"] == data["snapshot_id"]
        hashes.add(compare.config_hash(json.dumps(cfg)))
        per_task.setdefault(row["task_id"], set()).add(cfg["task_manifest_sha256"])
    sides = {}
    for variant in VARIANTS:
        reps = [reports[r["run_id"]] for r in data["runs"] if r["variant"] == variant and r.get("run_id")]
        sides[variant] = {"routing": VARIANTS[variant].to_dict(), **compare._side(reps),
                          "routing_requests": sum(r["iterations"]["routing_requests"] for r in reps),
                          "generation_requests": sum(r["iterations"]["generation_requests"] for r in reps)}
    complete = len(reports) == len(data["runs"]) and all(r["status"] != "running" for r in reports.values())
    return {**data, "sides": sides, "fair": complete and routing_matches and len(hashes) == 1
            and all(len(v) == 1 for v in per_task.values()), "shared_config_hashes": sorted(hashes),
            "comparison_variable": "routing only; initial memory routing disabled; same task, snapshot, generation models, budgets and evaluator",
            "interpretation": "All HTTP calls consume the same request/token/time budget. Router latency and cost "
                              "are included; reuse can finish a run before any router is called."}


def execute(task_ids: list[str], snapshot_id: str, repeats: int = 1, *, limits: config.RunLimits | None = None) -> dict:
    rows = plan(task_ids, repeats)
    compare.check_inputs(task_ids, snapshot_id, snapshot_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    ablation_id = f"routing-{stamp}-{uuid.uuid4().hex[:4]}"
    out = config.VAR_DIR / "routing-ablations" / f"{ablation_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    limits = limits or config.RunLimits()
    data = {"ablation_id": ablation_id, "status": "running", "snapshot_id": snapshot_id, "task_ids": task_ids,
            "repeats": repeats, "limits": limits.to_dict(), "runs": rows, "created_at": db.now(), "artifact": str(out)}
    lock = compare._try_lock()
    if lock is None:
        raise RuntimeError("another comparison is executing")
    try:
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        for row in rows:
            try:
                runner = Runner(RunOptions(task_id=row["task_id"], mode="eval", snapshot_id=snapshot_id, limits=limits,
                                            router=False, routing=config.RoutingConfig(**row["routing"]),
                                            label=f"{ablation_id} {row['variant']} r{row['repeat']}"))
                row["run_id"] = runner.create()
                out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                rep = runner.execute()
                row["status"], row["stop_reason"] = rep["status"], rep["stop_reason"]
                if rep["stop_reason"] in {"user_stopped", "environment_error", "internal_error", "model_api_error"}:
                    data["status"] = "stopped" if rep["stop_reason"] == "user_stopped" else "failed"
                    break
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                data["status"] = "failed"
                break
            finally:
                out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            data["status"] = "completed"
        data["ended_at"] = db.now()
        summary = summarize(data)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
