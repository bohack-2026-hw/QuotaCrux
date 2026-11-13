"""HTTP API for the frontend. Progress is read by polling /events; there is no token streaming."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import compare, config, db, memory, report, taskpkg
from .agent.runner import RunBusy, RunOptions, Runner

config.load_dotenv()
app = FastAPI(title="RouteEvo", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

SCRIPTS_DIR = config.BACKEND_DIR / "tests" / "fixtures" / "scripts"


class StartRun(BaseModel):
    task_id: str
    mode: str = "eval"
    snapshot_id: str | None = None
    label: str | None = None
    # Name of a scripted-model fixture (functional demo only); omit for real models.
    script: str | None = None


@app.get("/api/health")
def health() -> dict:
    running = db.one("SELECT run_id FROM runs WHERE status = 'running' ORDER BY started_at DESC LIMIT 1")
    return {"ok": True, "running_run_id": running["run_id"] if running else None}


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    out = []
    for r in db.all_rows("SELECT task_id, split, manifest_json, manifest_sha256 FROM tasks ORDER BY task_id"):
        m = json.loads(r["manifest_json"])
        out.append({"task_id": r["task_id"], "split": r["split"], "notes": m.get("notes"),
                    "target": m["target"], "dev_params": m["dev_params"], "manifest_sha256": r["manifest_sha256"]})
    return out


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    try:
        t = taskpkg.load(task_id, verify=False)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    # Only agent-visible material plus the public target; hidden data never leaves the evaluator.
    return {"task_id": t.task_id, "split": t.split, "target": t.manifest["target"], "contract": t.contract,
            "initial_code": t.initial_code, "examples": t.examples, "dev_profile": t.dev_profile,
            "default_limits": config.RunLimits().to_dict()}


@app.get("/api/runs")
def list_runs(task_id: str | None = None, limit: int = 50) -> list[dict]:
    sql = ("SELECT run_id, task_id, mode, snapshot_id, status, stop_reason, best_candidate_id, config_fingerprint,"
           " started_at, ended_at FROM runs")
    params: tuple = ()
    if task_id:
        sql, params = sql + " WHERE task_id = ?", (task_id,)
    return [dict(r) for r in db.all_rows(sql + " ORDER BY started_at DESC LIMIT ?", (*params, limit))]


@app.post("/api/runs", status_code=202)
def start_run(body: StartRun) -> dict:
    script = None
    if body.script:
        script = (SCRIPTS_DIR / f"{Path(body.script).stem}.json").resolve()
        if not script.exists():
            raise HTTPException(404, f"no scripted fixture {body.script!r}")
    compare.recover_stale()
    busy = db.one("SELECT comparison_id FROM comparisons WHERE status = 'running'")
    if busy:
        raise HTTPException(409, f"comparison {busy['comparison_id']} is running")
    try:
        runner = Runner(RunOptions(task_id=body.task_id, mode=body.mode, snapshot_id=body.snapshot_id,
                                   label=body.label, script=script))
        run_id = runner.create()
    except RunBusy as exc:
        raise HTTPException(409, str(exc)) from None
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from None
    threading.Thread(target=runner.execute, name=f"run-{run_id}", daemon=True).start()
    return {"run_id": run_id, "snapshot_id": runner.snapshot_id}


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str) -> dict:
    row = db.one("SELECT status FROM runs WHERE run_id = ?", (run_id,))
    if not row:
        raise HTTPException(404, "run not found")
    if row["status"] != "running":
        raise HTTPException(409, f"run is {row['status']}")
    db.update("runs", "run_id", run_id, {"stop_requested": 1})
    return {"run_id": run_id, "stop_requested": True, "note": "the run stops after its current step"}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        return report.build(run_id)
    except KeyError:
        raise HTTPException(404, "run not found") from None


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: str, after: int = 0) -> dict:
    rows = db.all_rows("SELECT event_id, ts, type, payload_json FROM events WHERE run_id = ? AND event_id > ? ORDER BY event_id",
                       (run_id, after))
    status = db.one("SELECT status FROM runs WHERE run_id = ?", (run_id,))
    if not status:
        raise HTTPException(404, "run not found")
    events = [{"event_id": r["event_id"], "ts": r["ts"], "type": r["type"], **json.loads(r["payload_json"])} for r in rows]
    return {"run_id": run_id, "status": status["status"], "events": events,
            "next_after": events[-1]["event_id"] if events else after}


@app.get("/api/runs/{run_id}/candidates/{candidate_id}")
def candidate_code(run_id: str, candidate_id: str) -> dict:
    row = db.one("SELECT * FROM candidates WHERE run_id = ? AND candidate_id = ?", (run_id, candidate_id))
    if not row:
        raise HTTPException(404, "candidate not found")
    return {**dict(row), "code": Path(row["code_path"]).read_text()}


class Activate(BaseModel):
    snapshot_id: str
    reason: str | None = None


@app.get("/api/snapshots")
def list_snapshots() -> dict:
    rows = db.all_rows("SELECT snapshot_id, version, parent_snapshot_id, source_run_id, created_at, diff_json FROM snapshots ORDER BY version")
    snaps = [{**{k: r[k] for k in r.keys() if k != "diff_json"}, "diff": json.loads(r["diff_json"]),
              "experience_count": len(memory.snapshot_experience_ids(r["snapshot_id"]))} for r in rows]
    history = [dict(h) for h in db.all_rows("SELECT * FROM pointer_history ORDER BY id DESC LIMIT 50")]
    return {"active_snapshot_id": memory.active_snapshot(), "snapshots": snaps, "pointer_history": history}


@app.get("/api/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> dict:
    try:
        return memory.snapshot(snapshot_id)
    except KeyError:
        raise HTTPException(404, "snapshot not found") from None


@app.get("/api/snapshots/{a}/diff/{b}")
def diff_snapshots(a: str, b: str) -> dict:
    return memory.compare_snapshots(a, b)


@app.put("/api/snapshots/active")
def activate_snapshot(body: Activate) -> dict:
    """Rollback / switch: only future runs are affected; records and running runs are untouched."""
    try:
        return memory.activate(body.snapshot_id, reason=body.reason or "switched from UI", actor="api")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    except memory.PointerLocked as exc:
        raise HTTPException(409, str(exc)) from None


@app.get("/api/experiences/{experience_id}")
def get_experience(experience_id: str) -> dict:
    try:
        return memory.experience(experience_id)
    except KeyError:
        raise HTTPException(404, "experience not found") from None


class StartComparison(BaseModel):
    task_ids: list[str]
    snapshot_a: str
    snapshot_b: str
    repeats: int = 3
    label: str | None = None
    script: str | None = None


@app.post("/api/comparisons", status_code=202)
def start_comparison(body: StartComparison) -> dict:
    script = None
    if body.script:
        script = (SCRIPTS_DIR / f"{Path(body.script).stem}.json").resolve()
        if not script.exists():
            raise HTTPException(404, f"no scripted fixture {body.script!r}")
    if db.one("SELECT run_id FROM runs WHERE status = 'running'"):
        raise HTTPException(409, "a run is in progress")
    try:
        cid = compare.create(body.task_ids, body.snapshot_a, body.snapshot_b, body.repeats, body.label,
                             str(script) if script else None)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from None
    threading.Thread(target=compare.execute, args=(cid,), name=f"cmp-{cid}", daemon=True).start()
    return {"comparison_id": cid}


@app.get("/api/comparisons")
def list_comparisons() -> list[dict]:
    rows = db.all_rows("SELECT comparison_id, status, label, plan_json, created_at, ended_at FROM comparisons ORDER BY created_at DESC")
    out = []
    for r in rows:
        p = json.loads(r["plan_json"])
        out.append({"comparison_id": r["comparison_id"], "status": r["status"], "label": r["label"], "tasks": p["tasks"],
                    "snapshot_a": p["snapshot_a"], "snapshot_b": p["snapshot_b"], "repeats": p["repeats"],
                    "created_at": r["created_at"], "ended_at": r["ended_at"]})
    return out


@app.get("/api/comparisons/{comparison_id}")
def get_comparison(comparison_id: str) -> dict:
    if not db.one("SELECT 1 FROM comparisons WHERE comparison_id = ?", (comparison_id,)):
        raise HTTPException(404, "comparison not found")
    return compare.summarize(comparison_id)


@app.post("/api/comparisons/{comparison_id}/stop")
def stop_comparison(comparison_id: str) -> dict:
    compare.request_stop(comparison_id)
    return {"comparison_id": comparison_id, "stop_requested": True}


# The built dashboard (frontend/dist) is served at / so one `routeevo serve` runs the whole demo.
# Mounted last so every /api route above takes precedence.
_DIST = config.BACKEND_DIR.parent / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="dashboard")
