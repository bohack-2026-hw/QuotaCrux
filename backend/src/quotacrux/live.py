"""Live progress for the dashboard: the operator's work plan and log, the running experiment and run, machine load.

Everything here is a cheap read (plain SQL, no report building) so it can be polled every few seconds during timed
experiments. The work plan lives in var/progress.json and is updated with `quotacrux progress ...`.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from . import config, db, memory

PROGRESS_PATH = config.VAR_DIR / "progress.json"
STATUSES = ("pending", "running", "done", "skipped", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return {"title": None, "steps": [], "log": []}


def _save(p: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1))
    tmp.replace(PROGRESS_PATH)


def plan(title: str, steps: list[tuple[str, str]]) -> dict:
    """Start a new work plan: (id, title) pairs, all pending. Keeps the log."""
    p = load_progress()
    p["title"] = title
    p["steps"] = [{"id": i, "title": t, "status": "pending", "note": None, "started_at": None, "ended_at": None} for i, t in steps]
    _save(p)
    return p


def step(step_id: str, status: str, note: str | None = None) -> dict:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    p = load_progress()
    s = next((x for x in p["steps"] if x["id"] == step_id), None)
    if s is None:
        s = {"id": step_id, "title": step_id, "status": "pending", "note": None, "started_at": None, "ended_at": None}
        p["steps"].append(s)
    s["status"] = status
    if note is not None:
        s["note"] = note
    if status == "running" and not s["started_at"]:
        s["started_at"] = _now()
    if status in ("done", "skipped", "failed"):
        s["ended_at"] = _now()
    p["log"].append({"ts": _now(), "text": f"{s['title']}：{ {'running': '开始', 'done': '完成', 'skipped': '跳过', 'failed': '失败', 'pending': '待办'}[status] }"
                     + (f" · {note}" if note else "")})
    _save(p)
    return p


def log(text: str) -> dict:
    p = load_progress()
    p["log"].append({"ts": _now(), "text": text})
    p["log"] = p["log"][-200:]
    _save(p)
    return p


# ---------- live view ----------

def _comparison(cid: str) -> dict:
    row = db.one("SELECT * FROM comparisons WHERE comparison_id = ?", (cid,))
    plan_ = json.loads(row["plan_json"])
    runs = db.all_rows(
        "SELECT cr.seq, cr.task_id, cr.arm, cr.repeat, cr.position, cr.snapshot_id, cr.run_id, cr.error, r.status, r.stop_reason,"
        " r.started_at, r.ended_at,"
        " (SELECT COUNT(*) FROM model_calls m WHERE m.run_id = r.run_id) AS requests,"
        " (SELECT COUNT(*) FROM model_calls m WHERE m.run_id = r.run_id AND m.role = 'large') AS large,"
        " (SELECT SUM(cost_usd) FROM model_calls m WHERE m.run_id = r.run_id) AS cost,"
        " (SELECT json_extract(result_json, '$.reason') FROM steps s WHERE s.run_id = r.run_id AND s.action = 'route_model') AS route,"
        " (SELECT COUNT(*) FROM candidates c WHERE c.run_id = r.run_id AND c.origin = 'experience') AS reused,"
        " (SELECT origin FROM candidates c WHERE c.run_id = r.run_id AND c.candidate_id = r.best_candidate_id) AS best_origin,"
        " e.speedup AS final_speedup, e.goal_met"
        " FROM comparison_runs cr LEFT JOIN runs r ON r.run_id = cr.run_id"
        " LEFT JOIN evaluations e ON e.evaluation_id = r.final_evaluation_id"
        " WHERE cr.comparison_id = ? ORDER BY cr.seq", (cid,))
    cells, durations = [], []
    totals: dict[str, dict] = {}
    for r in runs:
        route = r["route"] or ("reuse" if r["run_id"] and r["requests"] == 0 and r["best_origin"] == "experience" else None)
        state = "planned" if not r["run_id"] else ("running" if r["status"] == "running" else "done")
        cells.append({"seq": r["seq"], "task_id": r["task_id"], "arm": r["arm"] or r["snapshot_id"], "repeat": r["repeat"],
                      "position": r["position"], "run_id": r["run_id"], "state": state, "status": r["status"],
                      "stop_reason": r["stop_reason"], "route": route, "requests": r["requests"], "large": r["large"],
                      "cost_usd": r["cost"], "final_speedup": r["final_speedup"],
                      "goal_met": None if r["goal_met"] is None else bool(r["goal_met"]), "error": r["error"]})
        if state == "done" and r["started_at"] and r["ended_at"]:
            durations.append((datetime.fromisoformat(r["ended_at"]) - datetime.fromisoformat(r["started_at"])).total_seconds())
            t = totals.setdefault(r["arm"] or r["snapshot_id"], {"runs": 0, "goal_met": 0, "large_requests": 0, "cost_usd": 0.0,
                                                                  "no_model": 0, "seconds": 0.0})
            t["runs"] += 1
            t["goal_met"] += bool(r["goal_met"])
            t["large_requests"] += r["large"]
            t["cost_usd"] = round(t["cost_usd"] + (r["cost"] or 0), 6)
            t["no_model"] += r["requests"] == 0
            t["seconds"] = round(t["seconds"] + durations[-1], 1)
    done = sum(1 for c in cells if c["state"] == "done")
    avg = sum(durations) / len(durations) if durations else None
    remaining = len(cells) - done
    return {"comparison_id": cid, "kind": plan_.get("kind", "snapshots"), "label": row["label"], "status": row["status"],
            "tasks": plan_["tasks"], "repeats": plan_["repeats"], "start_snapshot": plan_.get("start_snapshot"),
            "snapshot_a": plan_.get("snapshot_a"), "snapshot_b": plan_.get("snapshot_b"),
            "planned": len(cells), "done": done, "created_at": row["created_at"], "ended_at": row["ended_at"],
            "avg_run_s": round(avg, 1) if avg else None, "eta_s": round(avg * remaining) if avg and row["status"] == "running" else None,
            "totals": totals, "cells": cells}


def _running_run() -> dict | None:
    r = db.one("SELECT run_id, task_id, mode, snapshot_id, started_at, config_json FROM runs WHERE status = 'running'"
               " ORDER BY started_at DESC LIMIT 1")
    if not r:
        return None
    route = db.one("SELECT result_json FROM steps WHERE run_id = ? AND action = 'route_model'", (r["run_id"],))
    steps = db.all_rows("SELECT seq, actor, action, status, purpose, candidate_id, json_extract(result_json, '$.speedup') AS speedup,"
                        " next_decision, ended_at FROM steps WHERE run_id = ? ORDER BY seq DESC LIMIT 8", (r["run_id"],))
    last = db.one("SELECT type, ts, payload_json FROM events WHERE run_id = ? ORDER BY event_id DESC LIMIT 1", (r["run_id"],))
    calls = db.one("SELECT COUNT(*) AS n, SUM(cost_usd) AS c FROM model_calls WHERE run_id = ?", (r["run_id"],))
    cfg = json.loads(r["config_json"])
    return {"run_id": r["run_id"], "task_id": r["task_id"], "mode": r["mode"], "snapshot_id": r["snapshot_id"],
            "label": cfg.get("label"), "started_at": r["started_at"],
            "elapsed_s": round((datetime.now(timezone.utc) - datetime.fromisoformat(r["started_at"])).total_seconds(), 1),
            "route": json.loads(route["result_json"]) if route else None, "requests": calls["n"], "cost_usd": calls["c"],
            "last_event": {"type": last["type"], "ts": last["ts"], "payload": json.loads(last["payload_json"])} if last else None,
            "steps": [dict(s) for s in reversed(steps)]}


def _load_samples(limit: int = 120) -> list[dict]:
    d = config.VAR_DIR / "env"
    files = sorted(d.glob("load-*.log"), key=lambda f: f.stat().st_mtime) if d.exists() else []
    out = []
    for line in (files[-1].read_text().splitlines()[-limit:] if files else []):
        try:
            ts, rest = line.split(" ", 1)
            out.append({"ts": ts, "load1": float(rest.strip("{} ").split()[0])})
        except (ValueError, IndexError):
            continue
    return out


def _icloud() -> str:
    try:
        out = subprocess.run(["ps", "-Ao", "stat=,comm="], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    for line in out.splitlines():
        if line.strip().endswith("/bird"):
            return "paused" if line.strip().startswith("T") else "running"
    return "not_running"


def live() -> dict:
    active_cmp = db.one("SELECT comparison_id FROM comparisons WHERE status = 'running' ORDER BY created_at DESC LIMIT 1")
    latest_cmp = active_cmp or db.one("SELECT comparison_id FROM comparisons ORDER BY created_at DESC LIMIT 1")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    spend = db.one("SELECT COUNT(*) AS n, SUM(cost_usd) AS c FROM model_calls WHERE role = 'large' AND started_at >= ?", (today,))
    return {
        "now": _now(),
        "progress": load_progress(),
        "comparison": _comparison(latest_cmp["comparison_id"]) if latest_cmp else None,
        "run": _running_run(),
        "machine": {"load": _load_samples(), "icloud_sync": _icloud(), "cpus": None},
        "active_snapshot": memory.active_snapshot(),
        "gpt_today": {"calls": spend["n"], "cost_usd": round(spend["c"] or 0, 4)},
    }


# ---------- system design summary ----------

def system_summary() -> dict:
    """How the work split between the local small model and the cloud large model over every finished real run, and
    which key node brought the large model in. Scripted runs are excluded; control arms are included (labelled)."""
    real = ("r.status IN ('completed', 'failed', 'stopped') AND (json_extract(r.config_json, '$.scripted') IS NULL"
            " OR json_extract(r.config_json, '$.scripted') = '[]')")
    runs = db.all_rows(f"SELECT r.run_id,"
                       " (SELECT COUNT(*) FROM model_calls m WHERE m.run_id = r.run_id AND m.role = 'small') AS small,"
                       " (SELECT COUNT(*) FROM model_calls m WHERE m.run_id = r.run_id AND m.role = 'large') AS large,"
                       " (SELECT origin FROM candidates c WHERE c.run_id = r.run_id AND c.candidate_id = r.best_candidate_id) AS best_origin,"
                       f" e.goal_met FROM runs r LEFT JOIN evaluations e ON e.evaluation_id = r.final_evaluation_id WHERE {real}")
    split = {"no_model": 0, "small_only": 0, "large_used": 0}
    for r in runs:
        split["no_model" if not (r["small"] or r["large"]) else "small_only" if not r["large"] else "large_used"] += 1
    calls = {r["role"]: {"requests": r["n"], "cost_usd": round(r["c"] or 0, 4), "unknown_cost": r["u"]} for r in db.all_rows(
        f"SELECT m.role, COUNT(*) AS n, SUM(m.cost_usd) AS c, SUM(m.cost_usd IS NULL AND m.cost_status = 'unknown') AS u"
        f" FROM model_calls m JOIN runs r USING (run_id) WHERE {real} GROUP BY m.role")}
    nodes = {"upgrade_two_misses": 0, "upgrade_small_cap": 0, "upgrade_decision_model": 0}
    for s in db.all_rows(f"SELECT s.result_json FROM steps s JOIN runs r USING (run_id) WHERE s.action = 'upgrade_model' AND {real}"):
        d = json.loads(s["result_json"] or "{}")
        if "decision" in str(d.get("rule", "")):
            nodes["upgrade_decision_model"] += 1
        elif (d.get("misses") or 0) >= 2:
            nodes["upgrade_two_misses"] += 1
        else:
            nodes["upgrade_small_cap"] += 1
    routes = {r["reason"]: r["n"] for r in db.all_rows(
        f"SELECT json_extract(s.result_json, '$.reason') AS reason, COUNT(*) AS n FROM steps s JOIN runs r USING (run_id)"
        f" WHERE s.action = 'route_model' AND {real} GROUP BY reason")}
    reuse_delivered = sum(1 for r in runs if not (r["small"] or r["large"]) and r["best_origin"] == "experience" and r["goal_met"])
    return {"runs": len(runs), "split": split, "calls": calls, "upgrades": nodes, "routes": routes,
            "reuse_delivered": reuse_delivered,
            "scope": "every finished run with real models in this store, including control arms (fresh / v0 / router off)"}
