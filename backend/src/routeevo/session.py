"""Two-round demo session: round 1 learns on one task from a base snapshot and publishes a new version; round 2
runs one unseen task under the base and the new snapshot (a one-repeat frozen comparison). No manual step in
between: models, prompt, tools, budgets and evaluator stay fixed; only the snapshot changes."""

from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import compare, db, memory
from .agent.runner import RunOptions, Runner

PHASES = ("round1_learning", "publishing", "round2_comparison", "done")


def create(learn_task: str, eval_task: str, base_snapshot: str) -> str:
    if learn_task == eval_task:
        raise ValueError("the second-round task must be different from the learning task")
    for t in (learn_task, eval_task):
        if not db.one("SELECT 1 FROM tasks WHERE task_id = ?", (t,)):
            raise KeyError(f"task {t} is not registered")
    if not db.one("SELECT 1 FROM snapshots WHERE snapshot_id = ?", (base_snapshot,)):
        raise KeyError(f"snapshot {base_snapshot} does not exist")
    sources = {memory.experience(e)["conditions"]["task_id"] for e in memory.snapshot_experience_ids(base_snapshot)}
    if eval_task in sources:
        raise ValueError(f"{eval_task} already contributed experience to {base_snapshot}; pick an unseen task")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    sid = f"ses-{stamp}-{uuid.uuid4().hex[:4]}"
    db.insert("sessions", {"session_id": sid, "learn_task": learn_task, "eval_task": eval_task,
                           "base_snapshot_id": base_snapshot, "phase": "created", "status": "running", "created_at": db.now()})
    return sid


def _set(sid: str, **fields) -> None:
    db.update("sessions", "session_id", sid, fields)


def execute(sid: str, script: Path | None = None) -> None:
    """`script` (scripted model, tests only) is never exposed through the API."""
    s = db.one("SELECT * FROM sessions WHERE session_id = ?", (sid,))
    try:
        _set(sid, phase="round1_learning")
        runner = Runner(RunOptions(task_id=s["learn_task"], mode="learn", snapshot_id=s["base_snapshot_id"],
                                   label=f"{sid} round 1", script=script))
        _set(sid, learn_run_id=runner.create())
        rep = runner.execute()
        new = rep["experience"]["published_snapshot_id"]
        _set(sid, phase="publishing", new_snapshot_id=new)
        if not new:
            _set(sid, status="completed", phase="done", detail="round 1 produced no qualifying experience; nothing to compare")
            return
        _set(sid, phase="round2_comparison")
        cid = compare.create([s["eval_task"]], s["base_snapshot_id"], new, 1, f"演示会话 {sid}", str(script) if script else None)
        _set(sid, comparison_id=cid)
        compare.execute(cid)
        _set(sid, status="completed", phase="done", ended_at=db.now())
    except Exception as exc:  # noqa: BLE001 - surfaced in the session row
        _set(sid, status="failed", detail=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}", ended_at=db.now())


def get(sid: str) -> dict:
    s = db.one("SELECT * FROM sessions WHERE session_id = ?", (sid,))
    if not s:
        raise KeyError(sid)
    return dict(s)
