"""Frozen within-task research comparisons with serial execution per VAR_DIR."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
from itertools import combinations
import json
import statistics
import uuid
from datetime import datetime, timezone

from . import compare, config, taskpkg
from .agent.runner import RunOptions, Runner
from .research_views import estimate_cost, validate_pricing

MODES = ("feedback", "independent", "no_feedback")
THREE_MODE_ORDERS = (("feedback", "no_feedback", "independent"),
                     ("no_feedback", "independent", "feedback"),
                     ("independent", "feedback", "no_feedback"))
RUNTIME_FIELDS = {"run_id", "status", "outcome", "best_candidate_id", "best_dev", "final_evaluation",
                  "final_status", "dev_status", "iterations", "timing", "usage", "cost", "progress",
                  "report_path", "comparison_config", "error", "task", "recorded_status"}


def comparable(rep: dict) -> dict:
    cfg = copy.deepcopy(rep["config"])
    for key in compare.NON_CONFIG_KEYS:
        cfg.pop(key, None)
    # Prompt text and visibility are the treatment; keep model, budgets, schema and affinity.
    cfg["prompt"].pop("system_sha256")
    cfg["research_protocol"].pop("mode")
    return {"config": cfg, "task_manifest_sha256": rep["config"]["task_manifest_sha256"],
            "environment": rep["environment"]}


def make_plan(task_ids: list[str], repeats: int, modes_by_task: dict[str, list[str]] | None = None) -> list[dict]:
    if not task_ids or len(set(task_ids)) != len(task_ids) or type(repeats) is not int or repeats < 1:
        raise ValueError("provide distinct task ids and positive repeats")
    modes_by_task = modes_by_task or {}
    if set(modes_by_task) - set(task_ids):
        raise ValueError("mode mapping contains an unplanned task")
    selections = {}
    for task_id in task_ids:
        modes = modes_by_task.get(task_id, ["feedback", "independent"])
        if (len(modes) != len(set(modes)) or set(modes) not in
                ({"feedback", "independent"}, set(MODES))):
            raise ValueError("each task must use feedback/independent or all three research modes")
        selections[task_id] = modes
    steps = []
    for repeat in range(1, repeats + 1):
        for index, task_id in enumerate(task_ids):
            if len(selections[task_id]) == 3:
                modes = THREE_MODE_ORDERS[(repeat - 1) % 3]
            else:
                modes = ("feedback", "independent") if (repeat - 1 + index) % 2 == 0 else ("independent", "feedback")
            for mode in modes:
                steps.append({"seq": len(steps) + 1, "task_id": task_id, "repeat": repeat, "mode": mode})
    return steps


def validate_plan(plan: list[dict], task_ids: list[str]) -> list[dict]:
    """Validate the entire supplied plan before constructing a runner or taking any model action."""
    if not isinstance(plan, list) or not plan:
        raise ValueError("research plan must be a non-empty list")
    if not task_ids or len(task_ids) != len(set(task_ids)):
        raise ValueError("provide distinct task ids")
    keys, seqs = set(), set()
    for item in plan:
        if not isinstance(item, dict) or not {"seq", "task_id", "repeat", "mode"} <= item.keys():
            raise ValueError("each plan entry needs seq, task_id, repeat and mode")
        if RUNTIME_FIELDS & item.keys():
            raise ValueError("plan entries must not contain runtime results")
        if item["task_id"] not in task_ids or item["mode"] not in MODES:
            raise ValueError("plan contains an unknown task or research mode")
        if any(type(item[k]) is not int or item[k] < 1 for k in ("seq", "repeat")):
            raise ValueError("plan seq and repeat must be positive integers")
        key = (item["task_id"], item["repeat"], item["mode"])
        if key in keys or item["seq"] in seqs:
            raise ValueError("plan contains duplicate seq or task/repeat/mode")
        keys.add(key)
        seqs.add(item["seq"])
    if {item["task_id"] for item in plan} != set(task_ids):
        raise ValueError("plan task ids differ from requested tasks")
    return copy.deepcopy(plan)


def _metric(step: dict) -> float | None:
    if step.get("final_status") != "completed":
        return None
    final = step.get("final_evaluation") or {}
    if not final.get("correct"):
        return None
    metric = (step.get("task") or {}).get("objective", {}).get("metric")
    return (final.get("objective") or {}).get("value") if metric == "score" else final.get("speedup")


def summarize(out: dict) -> dict:
    """Rebuild summaries and fairness from stored JSON, including merged worker artifacts."""
    runs = out["runs"]
    groups, pairs, known = [], [], {}
    mixed = []
    for step in runs:
        frozen = step.get("comparison_config")
        if frozen is not None:
            previous = known.setdefault(step["task_id"], frozen)
            if previous != frozen and step["task_id"] not in mixed:
                mixed.append(step["task_id"])
    all_finished = bool(runs) and all(r.get("status") == "completed" for r in runs)
    enough_modes = all(len({r["mode"] for r in runs if r["task_id"] == task_id}) >= 2
                       for task_id in {r["task_id"] for r in runs})
    complete_configs = all(r.get("comparison_config") is not None for r in runs)
    all_recorded = bool(runs) and all(r.get("status") in ("completed", "failed", "stopped", "interrupted")
                                    for r in runs) and complete_configs
    out["fair"] = False if mixed else (True if all_recorded and enough_modes else None)
    out["fairness"] = {"tasks_with_mixed_configurations": mixed,
                       "all_planned_runs_completed": all_finished, "all_planned_runs_recorded": all_recorded,
                       "all_configurations_recorded": complete_configs}
    for task_id in dict.fromkeys(r["task_id"] for r in runs):
        task_rows = [r for r in runs if r["task_id"] == task_id]
        task = next((r["task"] for r in task_rows if r.get("task")), {"task_id": task_id})
        mode_groups = []
        for mode in MODES:
            rows = [r for r in task_rows if r["mode"] == mode]
            if not rows:
                continue
            values = [_metric(r) for r in rows]
            usable = [x for x in values if x is not None]
            recorded = [r for r in rows if r.get("usage") is not None]
            ledger = {"requests": sum(r["usage"].get("requests", 0) for r in recorded),
                      "latency_s": sum(r["usage"].get("latency_s", 0) for r in recorded),
                      "errors": dict(sum((Counter(r["usage"].get("errors", {})) for r in recorded), Counter()))}
            for key in ("input_tokens", "output_tokens"):
                counts = [r["usage"].get(key) for r in recorded]
                ledger[key] = sum(x for x in counts if x is not None) if any(x is not None for x in counts) else (0 if not counts else None)
                ledger[f"{key}_unknown_calls"] = sum(r["usage"].get(f"{key}_unknown_calls", 0) for r in recorded)
                if any(x is None for x in counts):
                    ledger[f"{key}_unknown_calls"] += 1
            mode_groups.append({"mode": mode, "planned": len(rows),
                "started": sum(r.get("run_id") is not None for r in rows),
                "completed": sum(r.get("status") == "completed" for r in rows),
                "failed": sum(r.get("status") in ("failed", "interrupted", "stopped") for r in rows),
                "not_run": sum(r.get("status", "not_run") == "not_run" for r in rows),
                "final_status_counts": dict(Counter(r.get("final_status", "not_run") for r in rows)),
                "final_correct": sum(r.get("final_status") == "completed" and
                                     bool((r.get("final_evaluation") or {}).get("correct")) for r in rows),
                "final_metric_observations": len(usable), "final_values": values,
                "final_metric_median": statistics.median(usable) if usable else None,
                "c0_deliveries": sum(r.get("best_candidate_id") == "c0" for r in rows),
                "candidates_proposed": sum(r.get("iterations", {}).get("candidates_proposed", 0) for r in rows),
                "candidates_passed": sum(r.get("iterations", {}).get("candidates_passed", 0) for r in rows),
                "usage": ledger, "cost": estimate_cost(ledger, out.get("price_snapshot")),
                "cost_scope": "recorded calls only; unexecuted slots remain in planned count",
                "wall_clock_s": sum((r.get("timing", {}).get("wall_clock_total_s") or 0) for r in rows)})
        groups.append({"task": task, "modes": mode_groups})
        for repeat in sorted({r["repeat"] for r in task_rows}):
            repeated = {r["mode"]: r for r in task_rows if r["repeat"] == repeat}
            planned_modes = [m for m in MODES if any(r["mode"] == m for r in task_rows)]
            for left, right in combinations(planned_modes, 2):
                a, b = repeated.get(left, {}), repeated.get(right, {})
                av, bv = _metric(a), _metric(b)
                complete = av is not None and bv is not None
                pairs.append({"task_id": task_id, "repeat": repeat, "mode_a": left, "mode_b": right,
                    "run_a": a.get("run_id"), "run_b": b.get("run_id"), "metric": task.get("objective", {}).get("metric"),
                    "value_a": av, "value_b": bv, "status": "completed" if complete else "missing_or_failed",
                    "difference_a_minus_b": av - bv if complete else None,
                    "relative_difference_over_b": (av - bv) / bv if complete and bv != 0 else None})
    out["summary"] = {"tasks": groups, "pairs": pairs, "planned": len(runs),
                      "not_run": sum(r.get("status", "not_run") == "not_run" for r in runs)}
    return out


def execute(task_ids: list[str], *, repeats: int = 1, limits: config.RunLimits, fixed_model: str = "small",
            final_evaluation: bool = True, label: str | None = None, measure: config.MeasureConfig | None = None,
            modes_by_task: dict[str, list[str]] | None = None, plan: list[dict] | None = None,
            pricing: dict | None = None, plan_id: str | None = None) -> dict:
    if plan is not None and modes_by_task is not None:
        raise ValueError("use an explicit plan or a generated mode mapping, not both")
    steps = validate_plan(plan if plan is not None else make_plan(task_ids, repeats, modes_by_task), task_ids)
    if fixed_model not in ("small", "large"):
        raise ValueError("fixed_model must be small or large")
    validate_pricing(pricing)
    if pricing is not None and config.default_model_configs()[fixed_model].model != pricing["model"]:
        raise ValueError("price snapshot model differs from the fixed generation model")
    tasks = {task_id: taskpkg.load(task_id) for task_id in task_ids}
    measure = measure or config.MeasureConfig()
    lock = compare._try_lock()
    if lock is None:
        raise RuntimeError("another comparison is executing")
    cid = f"research-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:4]}"
    path = config.VAR_DIR / "comparisons" / f"{cid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {"comparison_id": cid, "status": "running", "label": label, "limits": limits.to_dict(),
           "measure": measure.to_dict(), "created_at": datetime.now(timezone.utc).isoformat(),
           "fixed_model": fixed_model, "final_evaluation": final_evaluation, "dev_only": not final_evaluation,
           "plan_id": plan_id, "plan": copy.deepcopy(steps),
           "plan_sha256": hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest(),
           "price_snapshot": copy.deepcopy(pricing), "runs": steps,
           "fair": None, "path": str(path), "protocol": "within-task-feedback-v2"}
    for step in steps:
        task = tasks[step["task_id"]]
        step.update(status="not_run", final_status="not_run" if final_evaluation else "disabled", dev_status="not_run",
                    task={"task_id": task.task_id, "family": task.family, "objective": task.objective,
                          "workload": task.presentation["workload"]})

    def save():
        summarize(out)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        temporary.replace(path)

    current = None
    try:
        save()
        for step in steps:
            current = step
            step["status"] = "running"
            step["final_status"] = "pending" if final_evaluation else "disabled"
            runner = Runner(RunOptions(task_id=step["task_id"], mode="eval", snapshot_id="v0",
                research_mode=step["mode"], fixed_model=fixed_model, final_evaluation=final_evaluation,
                limits=limits, measure=measure, label=f"{plan_id or cid} #{step['seq']} r{step['repeat']}"))
            step["run_id"] = runner.create()
            save()
            rep = runner.execute()
            best = rep["best_candidate"]
            dev = best["dev_evaluations"][-1] if best and best["dev_evaluations"] else None
            final_status = rep["outcome"]["final_status"]
            step.update(status=rep["status"], stop_reason=rep["stop_reason"], outcome=rep["outcome"], task=rep["task"],
                        best_candidate_id=best["candidate_id"] if best else None, best_dev=dev,
                        final_evaluation=rep["final_evaluation"], final_status=final_status,
                        dev_status=dev["status"] if dev else "not_run", comparison_config=comparable(rep),
                        iterations=rep["iterations"], timing=rep["timing"], usage=rep["usage"]["total"],
                        cost=estimate_cost(rep["usage"]["total"], pricing),
                        progress=copy.deepcopy(rep["progress"]), report_path=str(runner.dir / "report.json"))
            if final_status == "failed" and step["status"] == "completed":
                step.update(status="failed", recorded_status="completed")
            for point in step["progress"]:
                point["cost"] = estimate_cost(point["usage"], pricing)
            save()
            if out["fair"] is False:
                raise RuntimeError("configuration or environment changed within a task comparison")
            if rep["status"] != "completed" or (final_evaluation and final_status != "completed"):
                out["status"] = "interrupted"
                break
        else:
            out["status"] = "completed"
    except BaseException as exc:
        if current is not None and current["status"] == "running":
            current.update(status="interrupted", final_status="not_run" if final_evaluation else "disabled",
                           error=f"{type(exc).__name__}: {exc}")
        out.update(status="interrupted", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        out["ended_at"] = datetime.now(timezone.utc).isoformat()
        try:
            save()
        finally:
            lock.close()
    return out
