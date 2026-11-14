"""HTTP API for the frontend. Progress is read by polling /events; there is no token streaming."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import compare, config, db, memory, report, research_views, taskpkg
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
    action_router: Literal["llm", "decisions"] = "llm"
    model_router: Literal["rule", "decisions"] = "rule"
    research_mode: Literal["legacy", "feedback", "independent", "no_feedback"] | None = None
    research_model_policy: Literal["fixed", "adaptive"] = "fixed"
    fixed_model: Literal["small", "large"] | None = None
    final_evaluation: bool = True


@app.get("/api/live")
def get_live() -> dict:
    """Live progress: operator work plan and log, the running experiment and run, machine load (cheap reads only)."""
    from . import live

    return live.live()


@app.get("/api/health")
def health() -> dict:
    running = db.one("SELECT run_id FROM runs WHERE status = 'running' ORDER BY started_at DESC LIMIT 1")
    return {"ok": True, "running_run_id": running["run_id"] if running else None}


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    out = []
    for r in db.all_rows("SELECT task_id, split, manifest_json, manifest_sha256 FROM tasks ORDER BY task_id"):
        m = json.loads(r["manifest_json"])
        from .benchmarks import get
        desc = get(m["family"]).presentation(m)
        out.append({"family": m["family"], "presentation": desc, "family_title": desc["title"], "workload": desc["workload"], "task_id": r["task_id"], "split": r["split"], "notes": m.get("notes"),
                    "target": m["target"], "dev_params": m["dev_params"], "manifest_sha256": r["manifest_sha256"]})
    return out


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    try:
        t = taskpkg.load(task_id, verify=False)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    # Only agent-visible material plus the public target; hidden data never leaves the evaluator.
    return {"task_id": t.task_id, "split": t.split, "family": t.family, "target": t.manifest["target"], "contract": t.contract,
            "initial_code": t.initial_code, "examples": t.examples, "dev_profile": t.dev_profile,
            "default_limits": config.RunLimits().to_dict()}


@app.get("/api/runs")
def list_runs(task_id: str | None = None, limit: int = 50) -> list[dict]:
    # The final-test outcome travels with each row: a run can stop on "goal reached" (dev data) and still miss the final test.
    sql = ("SELECT r.run_id, r.task_id, r.mode, r.snapshot_id, r.status, r.stop_reason, r.best_candidate_id, r.config_fingerprint,"
           " r.started_at, r.ended_at, e.goal_met AS final_goal_met, e.speedup AS final_speedup,"
           " json_extract(e.detail_json, '$.objective.value') AS final_score, r.config_json AS _config,"
           " e.status AS _final_status, e.correct AS _final_correct, e.candidate_id AS _final_candidate,"
           " json_extract(t.manifest_json, '$.target.min_speedup') AS _target"
           " FROM runs r LEFT JOIN evaluations e ON e.evaluation_id = r.final_evaluation_id"
           " JOIN tasks t ON t.task_id=r.task_id")
    params: tuple = ()
    if task_id:
        sql, params = sql + " WHERE r.task_id = ?", (task_id,)
    out = []
    for row in db.all_rows(sql + " ORDER BY r.started_at DESC LIMIT ?", (*params, limit)):
        item = dict(row)
        protocol = json.loads(item.pop("_config")).get("research_protocol", {})
        status, correct = item.pop("_final_status"), item.pop("_final_correct")
        target, candidate = item.pop("_target"), item.pop("_final_candidate")
        normalized = (target is not None and candidate == "c0"
                      and status == "passed" and bool(correct))
        item.update(research_mode=protocol.get("mode", "legacy"), dev_only=protocol.get("final_evaluation") is False)
        item["final_status"], item["final_error"] = report.final_state(
            item["run_id"], item["status"], not item["dev_only"],
            {"status": status, "correct": correct} if status is not None else None)
        if normalized:
            item["final_speedup"] = 1.0
        item["final_normalized"] = normalized
        if item["final_status"] == "failed" and item["status"] == "completed":
            item["recorded_status"], item["status"] = item["status"], "failed"
        out.append(item)
    return out


@app.get("/api/research-comparisons")
def list_research_comparisons() -> list[dict]:
    try:
        return research_views.list_comparisons()
    except (ValueError, KeyError) as exc:
        raise HTTPException(500, f"invalid research comparison artifact: {exc}") from None


@app.get("/api/research-comparisons/{comparison_id}")
def get_research_comparison(comparison_id: str) -> dict:
    try:
        return research_views.load(comparison_id)
    except KeyError:
        raise HTTPException(404, "research comparison not found") from None
    except ValueError as exc:
        raise HTTPException(500, f"invalid research comparison artifact: {exc}") from None


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
                                   label=body.label, script=script,
                                   research_mode=body.research_mode, research_model_policy=body.research_model_policy,
                                   fixed_model=body.fixed_model, final_evaluation=body.final_evaluation,
                                   routing=config.RoutingConfig(action=body.action_router, model=body.model_router)))
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


@app.get("/api/runs/{run_id}/markdown", response_class=PlainTextResponse)
def run_markdown(run_id: str) -> str:
    from .narrative import run_markdown as build

    if not db.one("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)):
        raise HTTPException(404, "run not found")
    return build(run_id)


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


class StartStream(BaseModel):
    task_ids: list[str]
    start_snapshot: str
    repeats: int = 1
    label: str | None = None
    script: str | None = None


@app.post("/api/streams", status_code=202)
def start_stream(body: StartStream) -> dict:
    script = None
    if body.script:
        script = (SCRIPTS_DIR / f"{Path(body.script).stem}.json").resolve()
        if not script.exists():
            raise HTTPException(404, f"no scripted fixture {body.script!r}")
    if db.one("SELECT run_id FROM runs WHERE status = 'running'"):
        raise HTTPException(409, "a run is in progress")
    try:
        cid = compare.create_stream(body.task_ids, body.start_snapshot, body.repeats, body.label, str(script) if script else None)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from None
    threading.Thread(target=compare.execute, args=(cid,), name=f"str-{cid}", daemon=True).start()
    return {"comparison_id": cid}


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
        out.append({"comparison_id": r["comparison_id"], "kind": p.get("kind", "snapshots"), "status": r["status"],
                    "label": r["label"], "tasks": p["tasks"],
                    "snapshot_a": p["snapshot_a"], "snapshot_b": p["snapshot_b"], "repeats": p["repeats"],
                    "created_at": r["created_at"], "ended_at": r["ended_at"]})
    return out


# Finished comparisons never change; summarising one builds every run's report, so keep the result per process.
_SUMMARY_CACHE: dict[tuple, dict] = {}


def _summary(comparison_id: str) -> dict:
    row = db.one("SELECT status, ended_at FROM comparisons WHERE comparison_id = ?", (comparison_id,))
    if not row:
        raise HTTPException(404, "comparison not found")
    if row["status"] == "running":
        return compare.summarize(comparison_id)
    key = (comparison_id, row["status"], row["ended_at"])
    if key not in _SUMMARY_CACHE:
        _SUMMARY_CACHE[key] = compare.summarize(comparison_id)
    return _SUMMARY_CACHE[key]


@app.get("/api/comparisons/{comparison_id}")
def get_comparison(comparison_id: str) -> dict:
    return _summary(comparison_id)


@app.get("/api/comparisons/{comparison_id}/note")
def comparison_note(comparison_id: str) -> dict:
    from .narrative import evolution_note

    row = db.one("SELECT status, ended_at FROM comparisons WHERE comparison_id = ?", (comparison_id,))
    if not row:
        raise HTTPException(404, "comparison not found")
    key = ("note", comparison_id, row["status"], row["ended_at"])
    if row["status"] == "running":
        return evolution_note(comparison_id)
    if key not in _SUMMARY_CACHE:
        _SUMMARY_CACHE[key] = evolution_note(comparison_id)
    return _SUMMARY_CACHE[key]


@app.post("/api/comparisons/{comparison_id}/stop")
def stop_comparison(comparison_id: str) -> dict:
    compare.request_stop(comparison_id)
    return {"comparison_id": comparison_id, "stop_requested": True}


class StartSession(BaseModel):
    learn_task: str
    eval_task: str
    base_snapshot_id: str = "v0"


@app.post("/api/sessions", status_code=202)
def start_session(body: StartSession) -> dict:
    from . import session

    compare.recover_stale()
    if db.one("SELECT run_id FROM runs WHERE status = 'running'") or db.one("SELECT 1 FROM comparisons WHERE status = 'running'"):
        raise HTTPException(409, "a run or comparison is in progress")
    try:
        sid = session.create(body.learn_task, body.eval_task, body.base_snapshot_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from None
    threading.Thread(target=session.execute, args=(sid,), name=sid, daemon=True).start()
    return {"session_id": sid}


@app.get("/api/sessions")
def list_sessions() -> list[dict]:
    return [dict(r) for r in db.all_rows("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 20")]


# The built dashboard (frontend/dist) is served at / so one `routeevo serve` runs the whole demo.
# Mounted last so every /api route above takes precedence.
_DIST = config.BACKEND_DIR.parent / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="dashboard")
