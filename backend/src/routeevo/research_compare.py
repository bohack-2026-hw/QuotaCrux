"""Serial, equal-budget within-task feedback versus independent attempts."""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone

from . import compare, config, taskpkg
from .agent.runner import RunOptions, Runner


def comparable(rep: dict) -> dict:
    cfg = copy.deepcopy(rep["config"])
    for key in compare.NON_CONFIG_KEYS:
        cfg.pop(key, None)
    # Prompt text and visibility are the experimental treatment; all other inputs stay fixed.
    cfg["prompt"].pop("system_sha256")
    cfg["research_protocol"].pop("mode")
    return {"config": cfg, "task_manifest_sha256": rep["config"]["task_manifest_sha256"],
            "environment": rep["environment"]}


def execute(task_ids: list[str], *, repeats: int, limits: config.RunLimits, fixed_model: str = "small",
            final_evaluation: bool = True, label: str | None = None, measure: config.MeasureConfig | None = None) -> dict:
    if repeats < 1 or not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("provide distinct task ids and positive repeats")
    for task_id in task_ids:
        taskpkg.load(task_id)
    measure = measure or config.MeasureConfig()
    lock = compare._try_lock()
    if lock is None:
        raise RuntimeError("another comparison is executing")
    cid = f"research-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:4]}"
    path = config.VAR_DIR / "comparisons" / f"{cid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    steps = [{"seq": s["seq"], "task_id": s["task_id"], "repeat": s["repeat"], "mode": s["snapshot_id"]}
             for s in compare.plan(task_ids, "feedback", "independent", repeats)]
    out = {"comparison_id": cid, "status": "running", "label": label, "limits": limits.to_dict(),
           "measure": measure.to_dict(),
           "fixed_model": fixed_model, "final_evaluation": final_evaluation, "runs": steps,
           "fair": None, "path": str(path), "protocol": "within-task-feedback-v1"}
    configs = {}

    def save():
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        temporary.replace(path)

    save()
    try:
        for step in steps:
            runner = Runner(RunOptions(task_id=step["task_id"], mode="eval", snapshot_id="v0",
                research_mode=step["mode"], fixed_model=fixed_model, final_evaluation=final_evaluation,
                limits=limits, measure=measure, label=f"{cid} #{step['seq']} r{step['repeat']}"))
            step["run_id"] = runner.create()
            save()
            rep = runner.execute()
            frozen = comparable(rep)
            previous = configs.setdefault(step["task_id"], frozen)
            if previous != frozen:
                out["fair"] = False
                raise RuntimeError("configuration or environment changed within a task comparison")
            best = rep["best_candidate"]
            dev = best["dev_evaluations"][-1] if best and best["dev_evaluations"] else None
            step.update(status=rep["status"], stop_reason=rep["stop_reason"], outcome=rep["outcome"],
                        best_candidate_id=best["candidate_id"] if best else None, best_dev=dev,
                        iterations=rep["iterations"], timing=rep["timing"], usage=rep["usage"]["total"],
                        progress=rep["progress"], report_path=str(runner.dir / "report.json"))
            save()
            if rep["status"] in ("failed", "stopped"):
                out["status"] = "interrupted"
                break
        else:
            out.update(status="completed", fair=True)
    except BaseException as exc:
        out.update(status="interrupted", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        save()
        lock.close()
    return out
