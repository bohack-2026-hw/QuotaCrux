"""Four routing variants, with portable within-task comparisons and complete call accounting."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
import statistics
import uuid

from . import compare, config, db, taskpkg
from .agent import routing
from .agent.runner import RunOptions, Runner
from .research_compare import RUNTIME_FIELDS, _metric
from .research_views import estimate_cost, validate_pricing

VARIANTS = {
    "baseline": config.RoutingConfig("llm", "rule"),
    "action_decisions": config.RoutingConfig("decisions", "rule"),
    "model_decisions": config.RoutingConfig("llm", "decisions"),
    "both_decisions": config.RoutingConfig("decisions", "decisions"),
}
TERMINAL = {"completed", "failed", "stopped", "interrupted"}


def make_plan(task_ids: list[str], repeats: int) -> list[dict]:
    if type(repeats) is not int or repeats < 1 or not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("provide unique tasks and positive integer repeats")
    variants, rows = list(VARIANTS), []
    for repeat in range(repeats):
        for index, task_id in enumerate(task_ids):
            offset = (repeat + index) % len(variants)
            for variant in variants[offset:] + variants[:offset]:
                rows.append({"seq": len(rows) + 1, "task_id": task_id, "repeat": repeat + 1,
                             "variant": variant, "routing": VARIANTS[variant].to_dict()})
    return rows


# Retain the original Python entry point used by the legacy routing CLI.
plan = make_plan


def validate_plan(rows: list[dict], task_ids: list[str]) -> list[dict]:
    if not isinstance(rows, list) or not rows or not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("provide a nonempty plan and distinct task ids")
    keys, seqs = set(), set()
    runtime = RUNTIME_FIELDS | {"execution", "usage_by_model", "usage_by_purpose", "routing_steps", "reproduce", "action_counts"}
    for row in rows:
        if not isinstance(row, dict) or not {"seq", "task_id", "repeat", "variant", "routing"} <= row.keys():
            raise ValueError("plan entries require seq, task_id, repeat, variant and routing")
        if runtime & row.keys():
            raise ValueError("plan entries must not contain runtime results")
        if row["task_id"] not in task_ids or row["variant"] not in VARIANTS:
            raise ValueError("plan contains an unknown task or variant")
        if row["routing"] != VARIANTS[row["variant"]].to_dict():
            raise ValueError("plan routing differs from its variant")
        if any(type(row[k]) is not int or row[k] < 1 for k in ("seq", "repeat")):
            raise ValueError("plan seq and repeat must be positive integers")
        key = (row["task_id"], row["repeat"], row["variant"])
        if key in keys or row["seq"] in seqs:
            raise ValueError("plan contains duplicate seq or task/repeat/variant")
        keys.add(key)
        seqs.add(row["seq"])
    if {row["task_id"] for row in rows} != set(task_ids):
        raise ValueError("plan task ids differ from requested tasks")
    return deepcopy(rows)


def comparable(rep: dict) -> dict:
    cfg = deepcopy(rep["config"])
    for key in compare.NON_CONFIG_KEYS:
        cfg.pop(key, None)
    # Only the two treatment switches differ. Keep prompt hashes, models and policy.
    for key in ("action", "model"):
        cfg["routing"].pop(key)
    return {"config": cfg, "task_manifest_sha256": rep["config"]["task_manifest_sha256"],
            "environment": deepcopy(rep["environment"])}


def _sum_usage(ledgers: list[dict]) -> dict:
    result = {key: sum(x.get(key, 0) for x in ledgers) for key in ("requests", "latency_s")}
    result["errors"] = dict(sum((Counter(x.get("errors", {})) for x in ledgers), Counter()))
    for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens"):
        known = [x[key] for x in ledgers if x.get(key) is not None]
        result[key] = sum(known) if known else (None if ledgers else 0)
        result[f"{key}_unknown_calls"] = sum(x.get(f"{key}_unknown_calls", int(x.get(key) is None)) for x in ledgers)
    return result


def costs(ledgers: dict[str, dict], pricing: dict) -> dict:
    by_model, by_currency = {}, {}
    for key, usage in ledgers.items():
        role, provider, model = key.split(":", 2)
        purpose = "routing" if role in ("router_action", "router_model") else "generation"
        snapshot = pricing.get("decisions" if purpose == "routing" else role)
        # A changed model cannot inherit another model's price.
        if snapshot and snapshot["model"] != model:
            snapshot = None
        cost = estimate_cost(usage, snapshot)
        known = cost["amount"]
        if known is None and snapshot and any(usage.get(k) is not None for k in ("input_tokens", "output_tokens")):
            partial = {"requests": usage.get("requests", 1),
                       "input_tokens": usage.get("input_tokens") or 0, "output_tokens": usage.get("output_tokens") or 0}
            known = estimate_cost(partial, snapshot)["amount"]
            cost["status"] = "partial"
        by_model[key] = {**cost, "known_amount": known, "purpose": purpose, "role": role,
                         "provider": provider, "model": model, "usage": deepcopy(usage)}
    for currency in sorted({x["currency"] for x in by_model.values() if x["currency"]}):
        items = [x for x in by_model.values() if x["currency"] == currency]
        known = [x["known_amount"] for x in items if x["known_amount"] is not None]
        complete = all(x["amount"] is not None for x in items)
        by_currency[currency] = {"amount": sum(x["amount"] for x in items) if complete else None,
            "known_amount": sum(known) if known else None,
            "status": "estimated" if complete else "partial" if known else "unknown"}
    return {"by_model": by_model, "by_currency": by_currency,
            "unpriced_model_ledgers": sum(x["currency"] is None for x in by_model.values()),
            "scope": "recorded calls only; unexecuted slots remain in planned count"}


def _group_ledgers(rows: list[dict]) -> dict:
    keys = sorted({key for row in rows for key in row.get("usage_by_model", {})})
    return {key: _sum_usage([row["usage_by_model"][key] for row in rows if key in row.get("usage_by_model", {})])
            for key in keys}


def _plan_hash(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def _execution_matches(row: dict, data: dict) -> bool:
    execution = row["execution"]
    actual = execution["routing"]
    protocol = row["comparison_config"]["config"]["research_protocol"]
    return (row["routing"] == VARIANTS[row["variant"]].to_dict()
            and all(actual[k] == v for k, v in row["routing"].items())
            and execution["task_id"] == row["task_id"] and execution["snapshot_id"] == data["snapshot_id"]
            and protocol["mode"] == data["research_mode"] and protocol["fixed_model"] is None
            and (data["research_mode"] == "legacy" or protocol.get("model_policy") == "adaptive")
            and row["comparison_config"]["config"]["router"]["version"] == "off")


def summarize(data: dict) -> dict:
    """Recompute solely from portable JSON; failed and unexecuted slots remain visible."""
    rows, frozen = data["runs"], data["plan"]
    plan_matches = (data["plan_sha256"] == _plan_hash(frozen) and len(rows) == len(frozen)
                    and all(all(row.get(k) == v for k, v in item.items()) for row, item in zip(rows, frozen)))
    known, mixed = {}, set()
    for row in rows:
        cfg = row.get("comparison_config")
        if cfg is not None:
            if known.setdefault(row["task_id"], cfg) != cfg or not _execution_matches(row, data):
                mixed.add(row["task_id"])
    matrix = all({r["variant"] for r in frozen if (r["task_id"], r["repeat"]) == key} == set(VARIANTS)
                 for key in {(r["task_id"], r["repeat"]) for r in frozen})
    recorded = bool(rows) and all(r.get("status") in TERMINAL and r.get("comparison_config") is not None for r in rows)
    data["fair"] = False if mixed or not plan_matches else True if recorded and matrix else None
    data["fairness"] = {"tasks_with_mixed_configurations": sorted(mixed), "plan_matches": plan_matches,
        "complete_variant_matrix": matrix, "all_planned_runs_recorded": recorded,
        "all_planned_runs_completed": all(r.get("status") == "completed" for r in rows),
        "all_final_evaluations_completed": all(r.get("final_status") == "completed" for r in rows)
        if data["final_evaluation"] else None}
    groups, pairs, interactions = [], [], []
    pricing = data.get("price_snapshots") or {}
    for task_id in dict.fromkeys(r["task_id"] for r in frozen):
        task_rows = [r for r in rows if r["task_id"] == task_id]
        task = next((r["task"] for r in task_rows if r.get("task")), {"task_id": task_id})
        variants = []
        for variant in VARIANTS:
            selected = [r for r in task_rows if r["variant"] == variant]
            values = [_metric(r) for r in selected]
            usable = [v for v in values if v is not None]
            passed = sum(r.get("iterations", {}).get("candidates_passed", 0) for r in selected)
            proposed = sum(r.get("iterations", {}).get("candidates_proposed", 0) for r in selected)
            upgraded = sum(r.get("iterations", {}).get("upgrades", 0) > 0 for r in selected)
            recorded_rows = [r for r in selected if r.get("usage") is not None]
            variants.append({"variant": variant, "routing": VARIANTS[variant].to_dict(), "planned": len(selected),
                "completed": sum(r.get("status") == "completed" for r in selected),
                "failed": sum(r.get("status") in TERMINAL - {"completed"} for r in selected),
                "not_run": sum(r.get("status", "not_run") == "not_run" for r in selected),
                "final_status_counts": dict(Counter(r.get("final_status", "not_run") for r in selected)),
                "final_correct": sum(r.get("final_status") == "completed" and
                                     bool((r.get("final_evaluation") or {}).get("correct")) for r in selected),
                "final_values": values, "final_metric_observations": len(usable),
                "final_metric_median": statistics.median(usable) if usable else None,
                "c0_deliveries": sum(r.get("best_candidate_id") == "c0" for r in selected),
                "candidates_proposed": proposed, "candidates_passed": passed,
                "candidate_pass_rate": passed / proposed if proposed else None,
                "upgraded_runs": upgraded, "upgrade_rate": upgraded / len(recorded_rows) if recorded_rows else None,
                "generation_roles": {role: sum(r.get("iterations", {}).get(f"{role}_model_requests", 0) for r in selected)
                                     for role in ("small", "large")},
                "action_counts": dict(sum((Counter(r.get("action_counts", {})) for r in selected), Counter())),
                "usage": _sum_usage([r["usage"] for r in recorded_rows]),
                "usage_by_purpose": {purpose: _sum_usage([r["usage_by_purpose"][purpose] for r in recorded_rows])
                                     for purpose in ("routing", "generation")},
                "cost": costs(_group_ledgers(selected), pricing),
                "timing": {key: sum(r.get("timing", {}).get(key) or 0 for r in selected)
                           for key in ("wall_clock_total_s", "model_wait_s", "dev_evaluation_s", "final_evaluation_s")}})
        groups.append({"task": task, "variants": variants})
        for repeat in sorted({r["repeat"] for r in frozen if r["task_id"] == task_id}):
            repeated = {r["variant"]: r for r in task_rows if r["repeat"] == repeat}
            values = {v: _metric(repeated.get(v, {})) for v in VARIANTS}
            for left, right in combinations(VARIANTS, 2):
                a, b = values[left], values[right]
                complete = a is not None and b is not None
                pairs.append({"task_id": task_id, "repeat": repeat, "variant_a": left, "variant_b": right,
                              "value_a": a, "value_b": b, "status": "completed" if complete else "missing_or_failed",
                              "difference_a_minus_b": a - b if complete else None})
            complete = all(v is not None for v in values.values())
            interactions.append({"task_id": task_id, "repeat": repeat, "status": "completed" if complete else "missing_or_failed",
                "both_minus_action_minus_model_plus_baseline": values["both_decisions"] - values["action_decisions"]
                - values["model_decisions"] + values["baseline"] if complete else None})
    data["summary"] = {"tasks": groups, "pairs": pairs, "interactions": interactions, "planned": len(frozen),
                       "not_run": sum(r.get("status", "not_run") == "not_run" for r in rows)}
    data["cost"] = costs(_group_ledgers(rows), pricing)
    data["sides"] = {v: {key: sum(r.get("iterations", {}).get(key, 0) for r in rows if r["variant"] == v)
                          for key in ("model_requests", "routing_requests", "generation_requests")} for v in VARIANTS}
    return data


def _record(row: dict, rep: dict) -> None:
    best = rep["best_candidate"]
    dev = best["dev_evaluations"][-1] if best and best["dev_evaluations"] else None
    row.update(status=rep["status"], stop_reason=rep["stop_reason"], outcome=rep["outcome"], task=rep["task"],
        best_candidate_id=best["candidate_id"] if best else None, best_dev=dev,
        final_evaluation=rep["final_evaluation"], final_status=rep["outcome"]["final_status"],
        dev_status=dev["status"] if dev else "not_run", comparison_config=comparable(rep),
        execution={"task_id": rep["task"]["task_id"], "snapshot_id": rep["snapshot_id"], "routing": rep["config"]["routing"]},
        iterations=rep["iterations"], timing=rep["timing"], usage=rep["usage"]["total"],
        usage_by_model=rep["usage"]["by_model"], usage_by_purpose=rep["usage"]["by_purpose"],
        progress=deepcopy(rep["progress"]), reproduce=rep["reproduce"],
        routing_steps=[{k: s[k] for k in ("seq", "action", "status", "result", "model_role", "model_call_id")}
                       for s in rep["steps"] if s["actor"] == "model" and s["action"] in ("route_action", "route_model")])
    if row["routing"]["action"] == "decisions":
        choices = [s["result"]["choice"].split(":", 1)[0] for s in row["routing_steps"]
                   if s["action"] == "route_action" and s["result"].get("choice")]
    else:
        choices = [s["action"] for s in rep["steps"] if s["actor"] == "model" and
                   s["action"] in ("analyze", "propose_candidate", "get_evidence", "run_validation", "finish")]
    row["action_counts"] = dict(Counter(choices))


def execute(task_ids: list[str], snapshot_id: str, repeats: int = 1, *, limits: config.RunLimits | None = None,
            measure: config.MeasureConfig | None = None, research_mode: str = "legacy", research_model_policy: str = "adaptive",
            final_evaluation: bool = True, plan: list[dict] | None = None, plan_id: str | None = None,
            pricing: dict | None = None, label: str | None = None) -> dict:
    if research_mode not in ("legacy", "feedback") or research_model_policy != "adaptive":
        raise ValueError("routing ablation requires legacy or feedback with adaptive models")
    if research_mode == "feedback" and snapshot_id != "v0":
        raise ValueError("feedback routing ablation requires the empty v0 snapshot")
    rows = validate_plan(plan if plan is not None else make_plan(task_ids, repeats), task_ids)
    if any(row.get("mode", research_mode) != research_mode for row in rows):
        raise ValueError("plan mode differs from requested research mode")
    compare.check_inputs(task_ids, snapshot_id, snapshot_id)
    tasks = {task_id: taskpkg.load(task_id) for task_id in task_ids}
    if research_mode == "legacy" and any(task.is_native for task in tasks.values()):
        raise ValueError("native routing ablation requires feedback mode")
    pricing = deepcopy(pricing or {})
    if not isinstance(pricing, dict) or set(pricing) - {"small", "large", "decisions"}:
        raise ValueError("price snapshots must be keyed by small, large or decisions")
    models = {**config.default_model_configs(), "decisions": routing.decision_config("router_action")}
    for role, snapshot in pricing.items():
        validate_pricing(snapshot)
        if snapshot and models[role].model != snapshot["model"]:
            raise ValueError(f"price snapshot model differs from {role} model")
    limits, measure = limits or config.RunLimits(), measure or config.MeasureConfig()
    cid = f"research-routing-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:4]}"
    path = config.VAR_DIR / "comparisons" / f"{cid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"comparison_id": cid, "ablation_id": cid, "study": "routing", "protocol": "within-task-routing-v2",
        "status": "running", "label": label, "snapshot_id": snapshot_id, "task_ids": task_ids,
        "research_mode": research_mode, "research_model_policy": research_model_policy,
        "final_evaluation": final_evaluation, "dev_only": not final_evaluation, "repeats": repeats,
        "limits": limits.to_dict(), "measure": measure.to_dict(), "variants": list(VARIANTS),
        "plan": deepcopy(rows), "plan_sha256": _plan_hash(rows), "plan_id": plan_id,
        "price_snapshots": pricing, "runs": rows, "created_at": db.now(), "artifact": str(path), "path": str(path)}
    for row in rows:
        task = tasks[row["task_id"]]
        row.update(mode=research_mode, status="not_run", final_status="not_run" if final_evaluation else "disabled",
                   cost=costs({}, pricing),
                   task={"task_id": task.task_id, "family": task.family, "objective": task.objective})
    lock = compare._try_lock()
    if lock is None:
        raise RuntimeError("another comparison is executing")

    def save():
        summarize(data)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        temporary.replace(path)

    current = None
    try:
        save()
        for row in rows:
            current = row
            row.update(status="running", final_status="pending" if final_evaluation else "disabled")
            options = dict(task_id=row["task_id"], mode="eval", snapshot_id=snapshot_id, limits=limits, measure=measure,
                research_mode=research_mode, fixed_model=None, router=False, final_evaluation=final_evaluation,
                routing=config.RoutingConfig(**row["routing"]), label=f"{plan_id or cid} #{row['seq']} {row['variant']} r{row['repeat']}")
            if research_mode == "feedback":
                options["research_model_policy"] = research_model_policy
            runner = Runner(RunOptions(**options))
            row["run_id"] = runner.create()
            save()
            rep = runner.execute()
            _record(row, rep)
            row.update(cost=costs(row["usage_by_model"], pricing), report_path=str(runner.dir / "report.json"))
            if final_evaluation and row["final_status"] != "completed" and row["status"] == "completed":
                row.update(status="failed", recorded_status="completed")
            save()
            if data["fair"] is False:
                raise RuntimeError("routing, configuration or environment changed within a task comparison")
            if row["status"] != "completed":
                data["status"] = "stopped" if row["stop_reason"] == "user_stopped" else "failed"
                break
        else:
            data["status"] = "completed"
    except BaseException as exc:
        if current is not None and current["status"] == "running":
            current.update(status="interrupted", final_status="not_run" if final_evaluation else "disabled",
                           error=f"{type(exc).__name__}: {exc}")
        data.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        data["ended_at"] = db.now()
        try:
            save()
        finally:
            lock.close()
    return data
