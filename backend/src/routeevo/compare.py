"""Frozen old-vs-new snapshot comparison on held-out tasks.

Same tasks, initial programs, models, prompt, tools, budgets and evaluator; only the snapshot differs. Runs are
serial and alternate the snapshot order per task and repeat. Nothing is written to the experience store.
"""

from __future__ import annotations

import fcntl
import json
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config, db, memory, report
from .agent.runner import RunOptions, Runner

LOCK_PATH = config.VAR_DIR / "compare.lock"


def _try_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(LOCK_PATH, "a+")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        return None
    return fd


def recover_stale() -> None:
    """Mark 'running' comparisons as interrupted when no process holds the comparison lock."""
    if not db.one("SELECT 1 FROM comparisons WHERE status = 'running'"):
        return
    fd = _try_lock()
    if fd is None:
        return
    try:
        db.get().execute("UPDATE comparisons SET status = 'interrupted', ended_at = COALESCE(ended_at, ?) WHERE status = 'running'",
                         (db.now(),))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def plan(task_ids: list[str], snapshot_a: str, snapshot_b: str, repeats: int) -> list[dict]:
    """Alternate which snapshot goes first per task and per repeat so drift does not favour one side."""
    out = []
    for rep in range(repeats):
        for i, task_id in enumerate(task_ids):
            pair = (snapshot_a, snapshot_b) if (rep + i) % 2 == 0 else (snapshot_b, snapshot_a)
            out += [{"task_id": task_id, "snapshot_id": s, "repeat": rep + 1} for s in pair]
    return [{"seq": n + 1, **p} for n, p in enumerate(out)]


def check_inputs(task_ids: list[str], snapshot_a: str, snapshot_b: str) -> None:
    for s in (snapshot_a, snapshot_b):
        if not db.one("SELECT 1 FROM snapshots WHERE snapshot_id = ?", (s,)):
            raise KeyError(f"snapshot {s} does not exist")
    for t in task_ids:
        if not db.one("SELECT 1 FROM tasks WHERE task_id = ?", (t,)):
            raise KeyError(f"task {t} is not registered")
    for s in (snapshot_a, snapshot_b):
        sources = {memory.experience(e)["conditions"]["task_id"] for e in memory.snapshot_experience_ids(s)}
        leaked = sorted(sources & set(task_ids))
        if leaked:
            raise ValueError(f"tasks {leaked} contributed experience to snapshot {s}; they are not held out")


def create(task_ids: list[str], snapshot_a: str, snapshot_b: str, repeats: int, label: str | None, script: str | None) -> str:
    check_inputs(task_ids, snapshot_a, snapshot_b)
    recover_stale()
    running = db.one("SELECT comparison_id FROM comparisons WHERE status = 'running'")
    if running:
        raise RuntimeError(f"comparison {running['comparison_id']} is still running")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cid = f"cmp-{stamp}-{uuid.uuid4().hex[:4]}"
    steps = plan(task_ids, snapshot_a, snapshot_b, repeats)
    db.insert("comparisons", {
        "comparison_id": cid, "status": "running", "label": label, "created_at": db.now(),
        "plan_json": db.dumps({"tasks": task_ids, "snapshot_a": snapshot_a, "snapshot_b": snapshot_b, "repeats": repeats,
                               "scripted": script, "order": "alternating per task and repeat, serial", "runs": steps}),
    })
    for s in steps:
        db.insert("comparison_runs", {"comparison_id": cid, "seq": s["seq"], "task_id": s["task_id"],
                                      "snapshot_id": s["snapshot_id"], "repeat": s["repeat"]})
    return cid


def execute(comparison_id: str) -> dict:
    lock = _try_lock()
    if lock is None:
        raise RuntimeError("another comparison is executing")
    try:
        return _execute(comparison_id)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _execute(comparison_id: str) -> dict:
    p = json.loads(db.one("SELECT plan_json FROM comparisons WHERE comparison_id = ?", (comparison_id,))["plan_json"])
    script = Path(p["scripted"]) if p.get("scripted") else None
    status = "completed"
    for step in p["runs"]:
        if db.one("SELECT stop_requested FROM comparisons WHERE comparison_id = ?", (comparison_id,))["stop_requested"]:
            status = "stopped"
            break
        key = (comparison_id, step["seq"])
        try:
            runner = Runner(RunOptions(task_id=step["task_id"], mode="eval", snapshot_id=step["snapshot_id"], script=script,
                                       label=f"{comparison_id} #{step['seq']} r{step['repeat']}"))
            run_id = runner.create()
            db.get().execute("UPDATE comparison_runs SET run_id = ? WHERE comparison_id = ? AND seq = ?", (run_id, *key))
            runner.execute()
        except Exception as exc:  # noqa: BLE001 - recorded per planned run; the comparison continues
            db.get().execute("UPDATE comparison_runs SET error = ? WHERE comparison_id = ? AND seq = ?",
                             (f"{type(exc).__name__}: {exc}", *key))
    db.update("comparisons", "comparison_id", comparison_id, {"status": status, "ended_at": db.now()})
    summary = summarize(comparison_id)
    db.update("comparisons", "comparison_id", comparison_id, {"summary_json": db.dumps(summary)})
    out = config.VAR_DIR / "comparisons"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{comparison_id}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 4) if xs else None


def _side(reports: list[dict]) -> dict:
    n = len(reports)
    goal = [r for r in reports if r["outcome"]["goal_met"]]
    speedups = [r["outcome"]["final_speedup"] for r in reports if r["outcome"]["final_speedup"] is not None]
    usage = [r["usage"]["total"] for r in reports]
    costs_known = [u["cost_usd"] for u in usage if u["cost_usd"] is not None]
    stop_reasons: dict[str, int] = {}
    for r in reports:
        stop_reasons[r["stop_reason"]] = stop_reasons.get(r["stop_reason"], 0) + 1

    def tok(key: str) -> dict:
        vals = [u[key] for u in usage]
        known = [v for v in vals if v is not None]
        return {"total": sum(known) if known else None, "median_per_run": _median(known),
                "runs_with_unknown": sum(u[f"{key}_unknown_calls"] > 0 for u in usage)}

    return {
        "runs": n,
        "goal_met": len(goal),
        "success_rate": round(len(goal) / n, 4) if n else None,
        "final_correct": sum(1 for r in reports if r["outcome"]["final_correct"]),
        "final_speedups": speedups,
        "final_speedup_median": _median(speedups),
        "no_improvement_runs": sum(1 for r in reports if r["outcome"]["best_is_initial"]),
        "input_tokens": tok("input_tokens"),
        "output_tokens": tok("output_tokens"),
        "cost_usd_total": round(sum(costs_known), 6) if costs_known else None,
        "cost_status": sorted({u["cost_status"] for u in usage}),
        "wall_clock_s_total": round(sum(r["timing"]["wall_clock_total_s"] or 0 for r in reports), 3),
        "agent_loop_s_median": _median([r["timing"]["agent_loop_s"] for r in reports if r["timing"]["agent_loop_s"] is not None]),
        "model_requests_median": _median([r["iterations"]["model_requests"] for r in reports]),
        "candidates_failed_total": sum(r["iterations"]["candidates_failed"] for r in reports),
        "candidates_no_gain_total": sum(r["iterations"]["candidates_no_gain"] for r in reports),
        "upgrades_total": sum(r["iterations"]["upgrades"] for r in reports),
        "stop_reasons": stop_reasons,
    }


def _learning_cost(snapshot_a: str, snapshot_b: str) -> dict:
    """Cost of the learn runs that built snapshot_b on top of snapshot_a (walking parent links)."""
    chain, cur = [], snapshot_b
    while cur and cur != snapshot_a:
        row = db.one("SELECT parent_snapshot_id, source_run_id FROM snapshots WHERE snapshot_id = ?", (cur,))
        if not row:
            break
        if row["source_run_id"]:
            chain.append(row["source_run_id"])
        cur = row["parent_snapshot_id"]
    if cur != snapshot_a:
        return {"in_lineage": False, "note": f"{snapshot_a} is not an ancestor of {snapshot_b}; learning cost not attributable"}
    reps = [report.build(r) for r in chain]
    usage = [r["usage"]["total"] for r in reps]
    known = [u["cost_usd"] for u in usage if u["cost_usd"] is not None]
    return {"in_lineage": True, "learn_runs": chain,
            "cost_usd": round(sum(known), 6) if known else None, "cost_status": sorted({u["cost_status"] for u in usage}),
            "input_tokens": sum(u["input_tokens"] or 0 for u in usage), "output_tokens": sum(u["output_tokens"] or 0 for u in usage),
            "wall_clock_s": round(sum(r["timing"]["wall_clock_total_s"] or 0 for r in reps), 3)}


def summarize(comparison_id: str) -> dict:
    row = db.one("SELECT * FROM comparisons WHERE comparison_id = ?", (comparison_id,))
    p = json.loads(row["plan_json"])
    a, b = p["snapshot_a"], p["snapshot_b"]
    rows = db.all_rows("SELECT * FROM comparison_runs WHERE comparison_id = ? ORDER BY seq", (comparison_id,))
    finished = [r for r in rows if r["run_id"] and db.one("SELECT status FROM runs WHERE run_id = ?", (r["run_id"],))["status"] != "running"]
    reports = {r["run_id"]: report.build(r["run_id"]) for r in finished}
    fingerprints = sorted({rep["config_fingerprint"] for rep in reports.values()})

    per_task = {}
    for t in p["tasks"]:
        entry = {}
        for s in (a, b):
            reps = [reports[r["run_id"]] for r in finished if r["task_id"] == t and r["snapshot_id"] == s]
            entry[s] = {
                "runs": [{"run_id": x["run_id"], "goal_met": x["outcome"]["goal_met"], "final_speedup": x["outcome"]["final_speedup"],
                          "stop_reason": x["stop_reason"], "model_requests": x["iterations"]["model_requests"],
                          "output_tokens": x["usage"]["total"]["output_tokens"], "cost_usd": x["usage"]["total"]["cost_usd"],
                          "wall_clock_s": x["timing"]["wall_clock_total_s"], "experiences_read": len(x["experience"]["read"])}
                         for x in reps],
                "goal_met": sum(1 for x in reps if x["outcome"]["goal_met"]),
                "final_speedup_median": _median([x["outcome"]["final_speedup"] for x in reps if x["outcome"]["final_speedup"] is not None]),
            }
        per_task[t] = entry

    return {
        "comparison_id": comparison_id, "status": row["status"], "label": row["label"],
        "tasks": p["tasks"], "snapshot_a": a, "snapshot_b": b, "repeats": p["repeats"],
        "scripted_model": bool(p.get("scripted")),
        "planned_runs": len(rows), "finished_runs": len(finished),
        "errors": [{"seq": r["seq"], "task_id": r["task_id"], "snapshot_id": r["snapshot_id"], "error": r["error"]} for r in rows if r["error"]],
        "fair": len(fingerprints) <= 1,
        "config_fingerprints": fingerprints,
        "sides": {s: _side([reports[r["run_id"]] for r in finished if r["snapshot_id"] == s]) for s in (a, b)},
        "per_task": per_task,
        "learning_cost": _learning_cost(a, b),
        "notes": [
            "Repeats measure run-to-run variance under a fixed snapshot; they do not repeat the learning process.",
            "Success = improved and final speedup >= target on the hidden final data; all runs are included.",
            "Costs are estimates from versioned price tables; local Qwen has no API fee and its machine cost is not accounted.",
        ],
    }


def request_stop(comparison_id: str) -> None:
    db.update("comparisons", "comparison_id", comparison_id, {"stop_requested": 1})
    for r in db.all_rows("SELECT run_id FROM comparison_runs WHERE comparison_id = ? AND run_id IS NOT NULL", (comparison_id,)):
        db.get().execute("UPDATE runs SET stop_requested = 1 WHERE run_id = ? AND status = 'running'", (r["run_id"],))
