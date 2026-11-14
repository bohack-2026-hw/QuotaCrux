"""Frozen old-vs-new snapshot comparison on held-out tasks.

Same tasks, initial programs, models, prompt, tools, budgets and evaluator; only the snapshot differs. Runs are
serial and alternate the snapshot order per task and repeat. Nothing is written to the experience store.
"""

from __future__ import annotations

import fcntl
import hashlib
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
    if p.get("kind") == "stream":
        return _execute_stream(comparison_id, p)
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


# Run config keys that legitimately differ between runs of a fair comparison (or are not configuration).
NON_CONFIG_KEYS = {"fingerprint", "environment", "label", "scripted", "fingerprint_excludes", "task_manifest_sha256"}


def config_hash(config_json: str) -> str:
    cfg = {k: v for k, v in json.loads(config_json).items() if k not in NON_CONFIG_KEYS}
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def _fairness(finished_rows) -> dict:
    """Fair = within each task both snapshots ran the identical fingerprint, and the configuration apart from the
    task itself (models, prompt, schema, limits, measurement, evaluator, image, retrieval) is identical overall."""
    per_task: dict[str, set] = {}
    cfg_hashes: set[str] = set()
    for r in finished_rows:
        run = db.one("SELECT config_fingerprint, config_json FROM runs WHERE run_id = ?", (r["run_id"],))
        per_task.setdefault(r["task_id"], set()).add(run["config_fingerprint"])
        cfg_hashes.add(config_hash(run["config_json"]))
    split = sorted(t for t, f in per_task.items() if len(f) > 1)
    return {"fair": not split and len(cfg_hashes) <= 1, "config_hashes": sorted(cfg_hashes), "tasks_with_mixed_fingerprints": split}


def _count(items: list[str]) -> dict:
    out: dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def _route_label(rep: dict) -> str:
    """reuse = delivered from re-validated experience before any model request; else the router's reason."""
    route = rep.get("route")
    if route:
        return route["reason"]
    if rep["iterations"]["model_requests"] == 0 and rep["outcome"].get("best_from_reuse"):
        return "reuse"
    return "no_model_request"


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
        "model_requests_total": sum(r["iterations"]["model_requests"] for r in reports),
        "runs_without_model_request": sum(1 for r in reports if r["iterations"]["model_requests"] == 0),
        "goal_met_from_reuse": sum(1 for r in reports if r["outcome"]["goal_met"] and r["outcome"].get("best_from_reuse")),
        "programs_reused_total": sum(r["iterations"].get("programs_reused", 0) for r in reports),
        "candidates_failed_total": sum(r["iterations"]["candidates_failed"] for r in reports),
        "candidates_no_gain_total": sum(r["iterations"]["candidates_no_gain"] for r in reports),
        "upgrades_total": sum(r["iterations"]["upgrades"] for r in reports),
        "large_model_requests_total": sum(r["iterations"].get("large_model_requests", 0) for r in reports),
        "runs_using_large_model": sum(1 for r in reports if r["iterations"].get("large_model_requests", 0)),
        "routes": _count([_route_label(r) for r in reports]),
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
    if p.get("kind") == "stream":
        return summarize_stream(comparison_id)
    a, b = p["snapshot_a"], p["snapshot_b"]
    rows = db.all_rows("SELECT * FROM comparison_runs WHERE comparison_id = ? ORDER BY seq", (comparison_id,))
    finished = [r for r in rows if r["run_id"] and db.one("SELECT status FROM runs WHERE run_id = ?", (r["run_id"],))["status"] != "running"]
    reports = {r["run_id"]: report.build(r["run_id"]) for r in finished}
    fairness = _fairness(finished)

    per_task = {}
    for t in p["tasks"]:
        entry = {}
        for s in (a, b):
            reps = [reports[r["run_id"]] for r in finished if r["task_id"] == t and r["snapshot_id"] == s]
            entry[s] = {
                "runs": [{"run_id": x["run_id"], "goal_met": x["outcome"]["goal_met"], "final_speedup": x["outcome"]["final_speedup"],
                          "stop_reason": x["stop_reason"], "model_requests": x["iterations"]["model_requests"],
                          "output_tokens": x["usage"]["total"]["output_tokens"], "cost_usd": x["usage"]["total"]["cost_usd"],
                          "wall_clock_s": x["timing"]["wall_clock_total_s"], "experiences_read": len(x["experience"]["read"]),
                          "agent_loop_s": x["timing"]["agent_loop_s"], "best_from_reuse": x["outcome"].get("best_from_reuse", False),
                          "programs_reused": x["iterations"].get("programs_reused", 0)}
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
        "fair": fairness["fair"],
        "config_fingerprints": fairness["config_hashes"],
        "tasks_with_mixed_fingerprints": fairness["tasks_with_mixed_fingerprints"],
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


# ---------- online stream: the same task sequence with and without accumulating experience ----------
#
# Arm "memory" runs each task in online mode on the snapshot the previous task of the same repeat published (deliver
# like eval, then publish what was verified). Arm "fresh" runs each task in eval mode on the start snapshot. Within a
# repeat the arms alternate which goes first per task; each repeat replays the learning process from the start snapshot,
# so repeats measure the learning itself, not only run-to-run noise. Every task is run before anything learned from it
# can be read (prequential), so no stream task is ever evaluated on its own experience.

ARMS = ("memory", "fresh")


def plan_stream(task_ids: list[str], repeats: int) -> list[dict]:
    out = []
    for rep in range(repeats):
        for i, task_id in enumerate(task_ids):
            arms = ARMS if (rep + i) % 2 == 0 else ARMS[::-1]
            out += [{"task_id": task_id, "arm": a, "repeat": rep + 1, "position": i + 1} for a in arms]
    return [{"seq": n + 1, **x} for n, x in enumerate(out)]


def create_stream(task_ids: list[str], start: str, repeats: int, label: str | None, script: str | None,
                  router: bool = True) -> str:
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("a stream runs each task once per repeat")
    check_inputs(task_ids, start, start)
    for t in task_ids:
        split = db.one("SELECT split FROM tasks WHERE task_id = ?", (t,))["split"]
        if split not in memory.LEARNABLE_SPLITS:
            raise ValueError(f"task {t} is in split {split}; the memory arm writes experience, so only "
                             f"{sorted(memory.LEARNABLE_SPLITS)} tasks can be streamed")
    recover_stale()
    running = db.one("SELECT comparison_id FROM comparisons WHERE status = 'running'")
    if running:
        raise RuntimeError(f"comparison {running['comparison_id']} is still running")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cid = f"str-{stamp}-{uuid.uuid4().hex[:4]}"
    steps = plan_stream(task_ids, repeats)
    db.insert("comparisons", {
        "comparison_id": cid, "status": "running", "label": label, "created_at": db.now(),
        "plan_json": db.dumps({"kind": "stream", "tasks": task_ids, "start_snapshot": start, "snapshot_a": start,
                               "snapshot_b": "memory", "repeats": repeats, "router": router, "scripted": script,
                               "arms": {"memory": "online mode, reads what the previous task of the same repeat published",
                                        "fresh": f"eval mode, every task reads {start}"},
                               "order": "tasks in the listed order; arms alternate per task and repeat; serial", "runs": steps}),
    })
    for x in steps:
        db.insert("comparison_runs", {"comparison_id": cid, "seq": x["seq"], "task_id": x["task_id"], "arm": x["arm"],
                                      "position": x["position"], "snapshot_id": start if x["arm"] == "fresh" else "pending",
                                      "repeat": x["repeat"]})
    return cid


def _execute_stream(comparison_id: str, p: dict) -> dict:
    script = Path(p["scripted"]) if p.get("scripted") else None
    start = p["start_snapshot"]
    chain = {rep: start for rep in range(1, p["repeats"] + 1)}
    pointer_before = memory.active_snapshot()
    status = "completed"
    try:
        for step in p["runs"]:
            if db.one("SELECT stop_requested FROM comparisons WHERE comparison_id = ?", (comparison_id,))["stop_requested"]:
                status = "stopped"
                break
            key = (comparison_id, step["seq"])
            memory_arm = step["arm"] == "memory"
            snap = chain[step["repeat"]] if memory_arm else start
            try:
                runner = Runner(RunOptions(task_id=step["task_id"], mode="online" if memory_arm else "eval", snapshot_id=snap,
                                           script=script, router=p.get("router", True),
                                           label=f"{comparison_id} #{step['seq']} r{step['repeat']} {step['arm']}"))
                run_id = runner.create()
                db.get().execute("UPDATE comparison_runs SET run_id = ?, snapshot_id = ? WHERE comparison_id = ? AND seq = ?",
                                 (run_id, snap, *key))
                runner.execute()
                if memory_arm:
                    published = db.one("SELECT published_snapshot_id FROM runs WHERE run_id = ?", (run_id,))["published_snapshot_id"]
                    chain[step["repeat"]] = published or snap
            except Exception as exc:  # noqa: BLE001 - recorded per planned run; the stream continues
                db.get().execute("UPDATE comparison_runs SET error = ? WHERE comparison_id = ? AND seq = ?",
                                 (f"{type(exc).__name__}: {exc}", *key))
    finally:
        # Online runs move the active pointer as they publish; a stream is an experiment, so put it back.
        if memory.active_snapshot() != pointer_before:
            memory.activate(pointer_before, reason=f"任务流 {comparison_id} 结束，恢复实验前的生效版本", actor="stream")
    db.update("comparisons", "comparison_id", comparison_id, {"status": status, "ended_at": db.now()})
    summary = summarize_stream(comparison_id)
    db.update("comparisons", "comparison_id", comparison_id, {"summary_json": db.dumps(summary)})
    out = config.VAR_DIR / "comparisons"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{comparison_id}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _stream_run(rep: dict, row) -> dict:
    u, it = rep["usage"]["total"], rep["iterations"]
    return {"run_id": rep["run_id"], "repeat": row["repeat"], "snapshot_id": rep["snapshot_id"], "route": _route_label(rep),
            "goal_met": rep["outcome"]["goal_met"], "final_speedup": rep["outcome"]["final_speedup"],
            "best_from_reuse": rep["outcome"].get("best_from_reuse", False), "model_requests": it["model_requests"],
            "large_model_requests": it.get("large_model_requests", 0), "upgrades": it["upgrades"],
            "cost_usd": u["cost_usd"], "output_tokens": u["output_tokens"], "input_tokens": u["input_tokens"],
            "agent_loop_s": rep["timing"]["agent_loop_s"], "wall_clock_s": rep["timing"]["wall_clock_total_s"],
            "published_snapshot_id": rep["experience"]["published_snapshot_id"],
            "experiences_published": len(rep["experience"]["published_experiences"]), "stop_reason": rep["stop_reason"]}


def summarize_stream(comparison_id: str) -> dict:
    from . import families

    row = db.one("SELECT * FROM comparisons WHERE comparison_id = ?", (comparison_id,))
    p = json.loads(row["plan_json"])
    rows = db.all_rows("SELECT * FROM comparison_runs WHERE comparison_id = ? ORDER BY seq", (comparison_id,))
    finished = [r for r in rows if r["run_id"] and db.one("SELECT status FROM runs WHERE run_id = ?", (r["run_id"],))["status"] != "running"]
    reports = {r["run_id"]: report.build(r["run_id"]) for r in finished}
    fairness = _fairness(finished)

    seen: set[str] = set()
    positions = []
    for i, t in enumerate(p["tasks"], start=1):
        m = json.loads(db.one("SELECT manifest_json FROM tasks WHERE task_id = ?", (t,))["manifest_json"])
        first = m["family"] not in seen
        seen.add(m["family"])
        arms = {a: [_stream_run(reports[r["run_id"]], r) for r in finished if r["task_id"] == t and r["arm"] == a] for a in ARMS}
        positions.append({"position": i, "task_id": t, "family": m["family"], "workload": families.get(m["family"]).describe(m["dev_params"]),
                          "first_of_family": first, "notes": m.get("notes"), "arms": arms})

    def series(arm: str, rep: int) -> dict:
        cost, loop, out = 0.0, 0.0, {"cost_usd": [], "agent_loop_s": [], "large_model_requests": []}
        large = 0
        for pos in positions:
            run = next((x for x in pos["arms"][arm] if x["repeat"] == rep), None)
            if run is None:
                break
            cost += run["cost_usd"] or 0
            loop += run["agent_loop_s"] or 0
            large += run["large_model_requests"]
            out["cost_usd"].append(round(cost, 6))
            out["agent_loop_s"].append(round(loop, 3))
            out["large_model_requests"].append(large)
        return out

    def group(arm: str, first: bool | None) -> dict:
        reps = [reports[r["run_id"]] for r in finished if r["arm"] == arm and
                (first is None or next(x for x in positions if x["task_id"] == r["task_id"])["first_of_family"] == first)]
        return _side(reps)

    by_family = {}
    for fam in sorted({x["family"] for x in positions}):
        ids = {x["task_id"] for x in positions if x["family"] == fam}
        by_family[fam] = {a: _side([reports[r["run_id"]] for r in finished if r["arm"] == a and r["task_id"] in ids]) for a in ARMS}

    growth = []
    for rep in range(1, p["repeats"] + 1):
        snaps = [x["published_snapshot_id"] for pos in positions for x in pos["arms"]["memory"] if x["repeat"] == rep and x["published_snapshot_id"]]
        last = snaps[-1] if snaps else p["start_snapshot"]
        growth.append({"repeat": rep, "start": p["start_snapshot"], "end": last, "published_versions": len(snaps),
                       "experiences_start": len(memory.snapshot_experience_ids(p["start_snapshot"])),
                       "experiences_end": len(memory.snapshot_experience_ids(last))})

    return {
        "comparison_id": comparison_id, "kind": "stream", "status": row["status"], "label": row["label"],
        "tasks": p["tasks"], "start_snapshot": p["start_snapshot"], "snapshot_a": p["start_snapshot"], "snapshot_b": "memory",
        "repeats": p["repeats"], "router": p.get("router", True), "arms": p["arms"],
        "scripted_model": bool(p.get("scripted")),
        "planned_runs": len(rows), "finished_runs": len(finished),
        "errors": [{"seq": r["seq"], "task_id": r["task_id"], "arm": r["arm"], "error": r["error"]} for r in rows if r["error"]],
        "fair": fairness["fair"], "config_fingerprints": fairness["config_hashes"],
        "tasks_with_mixed_fingerprints": fairness["tasks_with_mixed_fingerprints"],
        "sides": {a: _side([reports[r["run_id"]] for r in finished if r["arm"] == a]) for a in ARMS},
        "first_of_family": {a: group(a, True) for a in ARMS},
        "repeats_of_family": {a: group(a, False) for a in ARMS},
        "by_family": by_family,
        "positions": positions,
        "series": {a: {str(rep): series(a, rep) for rep in range(1, p["repeats"] + 1)} for a in ARMS},
        "growth": growth,
        "notes": [
            "Memory arm: online mode, each task reads what the previous task of the same repeat published. Fresh arm: eval "
            "mode on the start snapshot. Same tasks, order and configuration; only accumulated experience differs.",
            "Each repeat replays the learning from the start snapshot, so repeats vary the learning process itself.",
            "Every task runs before anything learned from it exists (prequential); no task reads its own experience.",
            "Costs are estimates from versioned price tables; local Qwen has no API fee and its machine cost is not accounted.",
        ],
    }
