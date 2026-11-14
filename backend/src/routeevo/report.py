"""Run report assembled from stored records only; usable for finished and in-progress runs."""

from __future__ import annotations

import json
import shlex
from datetime import datetime

from . import db, research
from .benchmarks import get as benchmark


def _secs(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds(), 3)


def _sum(rows, key: str) -> tuple[int | None, int]:
    """Sum a nullable column over calls that have usage at all; return (sum or None, number of unknown rows).

    A run that made no model request at all used 0 tokens (known), not an unknown amount."""
    if not rows:
        return 0, 0
    vals = [r[key] for r in rows if r["usage_source"] != "not_applicable"]
    unknown = sum(1 for v in vals if v is None)
    known = [v for v in vals if v is not None]
    return (sum(known) if known else None), unknown


def _ledger(calls) -> dict:
    out = {"requests": len(calls), "ok": sum(1 for c in calls if c["status"] == "ok"),
           "errors": {}, "latency_s": round(sum(c["latency_s"] or 0 for c in calls), 3)}
    for c in calls:
        if c["error_kind"]:
            out["errors"][c["error_kind"]] = out["errors"].get(c["error_kind"], 0) + 1
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
        total, unknown = _sum(calls, key)
        out[key] = total
        out[f"{key}_unknown_calls"] = unknown
    costs = [c for c in calls if c["cost_status"] not in ("not_applicable", "not_billed")]
    known = [c["cost_usd"] for c in costs if c["cost_usd"] is not None]
    unknown = sum(1 for c in costs if c["cost_usd"] is None)
    out["cost_usd"] = round(sum(known), 6) if known else (0.0 if not costs else None)
    out["cost_status"] = "no_model_calls" if not calls else "unknown" if unknown and not known else ("partial" if unknown else
                         ("estimated" if any(c["cost_status"] == "estimated" for c in costs) else
                          ("local_no_api_fee" if costs else "not_applicable")))
    out["cost_unknown_calls"] = unknown
    out["price_versions"] = sorted({c["price_version"] for c in calls if c["price_version"]})
    return out


def build(run_id: str) -> dict:
    run = db.one("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    if not run:
        raise KeyError(run_id)
    cfg = json.loads(run["config_json"])
    task = db.one("SELECT task_id, split, manifest_json FROM tasks WHERE task_id = ?", (run["task_id"],))
    manifest = json.loads(task["manifest_json"])
    target = manifest["target"]["min_speedup"]
    steps = db.all_rows("SELECT * FROM steps WHERE run_id = ? ORDER BY seq", (run_id,))
    calls = db.all_rows("SELECT * FROM model_calls WHERE run_id = ? ORDER BY started_at", (run_id,))
    tools = db.all_rows("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY started_at", (run_id,))
    evals = db.all_rows("SELECT * FROM evaluations WHERE run_id = ? ORDER BY started_at", (run_id,))
    cands = db.all_rows("SELECT * FROM candidates WHERE run_id = ? ORDER BY seq", (run_id,))

    dev_evals = [e for e in evals if e["dataset"] == "dev"]
    final = next((e for e in evals if e["evaluation_id"] == run["final_evaluation_id"]), None)
    best_id = run["best_candidate_id"]

    cand_out = []
    for c in cands:
        mine = [e for e in dev_evals if e["candidate_id"] == c["candidate_id"]]
        cand_out.append({
            "candidate_id": c["candidate_id"], "origin": c["origin"], "parent_candidate_id": c["parent_candidate_id"],
            "code_path": c["code_path"], "code_sha256": c["code_sha256"], "model_call_id": c["model_call_id"],
            "dev_evaluations": [{"evaluation_id": e["evaluation_id"], "status": e["status"], "correct": e["correct"],
                                 "speedup": e["speedup"], "improved": e["improved"], "goal_met": e["goal_met"],
                                 "objective": json.loads(e["detail_json"]).get("objective"),
                                 "eligible_for_selection": json.loads(e["detail_json"]).get("eligible_for_selection", True)} for e in mine],
        })
    model_cands = [c for c in cand_out if c["origin"] == "model"]
    reused = [c for c in cand_out if c["origin"] == "experience"]
    latest = {c["candidate_id"]: (c["dev_evaluations"][-1] if c["dev_evaluations"] else None) for c in model_cands + reused}
    passed_all = [cid for cid, e in latest.items() if e and e["status"] == "passed"]
    improved_all = [cid for cid in passed_all if latest[cid]["improved"] and latest[cid]["eligible_for_selection"]]
    model_ids = {c["candidate_id"] for c in model_cands}
    passed = [cid for cid in passed_all if cid in model_ids]
    improved = [cid for cid in improved_all if cid in model_ids]
    raised = next((s for s in steps if s["action"] == "set_target"), None)

    final_out = None
    if final:
        detail = json.loads(final["detail_json"])
        final_out = {
            "evaluation_id": final["evaluation_id"], "candidate_id": final["candidate_id"], "status": final["status"],
            "correct": bool(final["correct"]) if final["correct"] is not None else None,
            "speedup": final["speedup"], "candidate_median_s": final["candidate_median_s"],
            "baseline_median_s": final["baseline_median_s"], "timing": detail.get("timing"),
            "failure": detail.get("failure"), "duration_s": detail.get("duration_s"),
            "objective": detail.get("objective"), "case_count": detail.get("case_count"), "passed_cases": detail.get("passed_cases"),
            "note": "initial program checked for correctness only; no improvement to measure" if final["candidate_id"] == "c0" else None,
        }
    goal_met = bool(final and final["goal_met"])

    by_role: dict[str, list] = {}
    for c in calls:
        by_role.setdefault(f"{c['role']}:{c['provider']}:{c['model_requested']}", []).append(c)
    loop_s = _secs(run["started_at"], run["loop_ended_at"])
    limit = cfg["limits"]["wall_clock_s"]
    upgrade_steps = [s for s in steps if s["action"] == "upgrade_model"]
    total_ledger = _ledger(calls)

    out = {
        "run_id": run_id,
        "task": {"task_id": run["task_id"], "split": task["split"], "target_min_speedup": target,
                 "objective": {"metric": "speedup", "direction": "maximize", **manifest["target"]},
                 "family": manifest["family"], "presentation": benchmark(manifest["family"]).presentation(manifest),
                 "dev_params": manifest["dev_params"], "final_params": manifest["final_params"],
                 "source": manifest.get("source"), "selection": manifest.get("selection")},
        "mode": run["mode"], "snapshot_id": run["snapshot_id"], "label": cfg.get("label"),
        "scripted_model": cfg.get("scripted") or [],
        "status": run["status"], "stop_reason": run["stop_reason"], "stop_detail": run["stop_detail"],
        "config_fingerprint": run["config_fingerprint"],
        "outcome": {
            "run_completed": run["status"] == "completed",
            "candidate_ran": any(e["executed"] for e in dev_evals if e["candidate_id"] != "c0"),
            "dev_validation_passed": bool(passed_all),
            "dev_improved": bool(improved_all),
            "best_from_reuse": any(c["candidate_id"] == best_id for c in reused),
            "best_is_initial": best_id == "c0",
            "final_evaluated": final is not None,
            "final_correct": final_out["correct"] if final_out else None,
            "final_speedup": final_out["speedup"] if final_out else None,
            "final_objective": final_out.get("objective") if final_out else None,
            "goal_met": goal_met,
            "valid_artifact": bool(final_out and final_out["correct"]) if final_out else None,
            "summary": _summary(run, best_id, final_out, goal_met),
        },
        "experience": {
            "snapshot_read": run["snapshot_id"],
            "retrieval": json.loads(run["retrieval_json"]) if run["retrieval_json"] else None,
            "read": [dict(r) for r in db.all_rows(
                "SELECT re.experience_id, re.rank, re.matching_features, e.outcome, e.task_id,"
                " json_extract(e.source_json, '$.run_id') AS source_run_id"
                " FROM run_experiences re JOIN experiences e USING (experience_id) WHERE re.run_id = ? ORDER BY re.rank", (run_id,))],
            "published_snapshot_id": run["published_snapshot_id"],
            "published_experiences": [r["experience_id"] for r in db.all_rows(
                "SELECT experience_id FROM experiences WHERE json_extract(source_json, '$.run_id') = ?", (run_id,))],
        },
        "best_candidate": next((c for c in cand_out if c["candidate_id"] == best_id), None),
        "best_rule": ("highest valid dev score within the research budget; else initial c0" if target is None else
                      "highest latest dev median speedup among passed eligible candidates whose samples all beat the baseline's; else initial c0"),
        "run_target_speedup": json.loads(raised["result_json"])["run_target_speedup"] if raised else target,
        "final_evaluation": final_out,
        "candidates": cand_out,
        "iterations": {
            "model_requests": len(calls),
            "candidates_proposed": len(model_cands),
            "candidates_passed": len(passed),
            "candidates_improved": len(improved),
            "candidates_no_gain": len(passed) - len(improved),
            "candidates_failed": len(model_cands) - len(passed),
            "programs_reused": len(reused),
            "programs_reused_improved": sum(1 for c in reused if c["candidate_id"] in improved_all),
            "invalid_actions": sum(1 for s in steps if s["status"] == "invalid_action"),
            "unusable_replies": sum(1 for s in steps if s["status"] == "unusable_reply"),
            "api_errors": sum(1 for s in steps if s["status"] == "api_error"),
            "evidence_calls": len(tools),
            "upgrades": len(upgrade_steps),
            "upgrade_at_step": upgrade_steps[0]["seq"] if upgrade_steps else None,
        },
        "usage": {
            "total": total_ledger,
            "by_model": {k: _ledger(v) for k, v in by_role.items()},
            "self_hosted_machine_cost": "unknown (not accounted)" if any(c["provider"] == "chat_compat" for c in calls) else None,
        },
        "timing": {
            "wall_clock_total_s": _secs(run["started_at"], run["ended_at"]),
            "agent_loop_s": loop_s,
            # Live view: seconds since the loop started (frozen once the loop ends).
            "agent_loop_elapsed_s": loop_s if loop_s is not None else _secs(run["started_at"], db.now()),
            "agent_loop_limit_s": limit,
            "agent_loop_overrun_s": round(max(0.0, loop_s - limit), 3) if loop_s is not None else None,
            "final_evaluation_s": final_out["duration_s"] if final_out else None,
            "model_wait_s": total_ledger["latency_s"],
            "dev_evaluation_s": round(sum(json.loads(e["detail_json"]).get("duration_s", 0) for e in dev_evals), 3),
            "evidence_tool_s": round(sum(t["duration_s"] or 0 for t in tools), 3),
            "container_startup_s": round(sum(json.loads(e["detail_json"]).get("container_ready_latency_s", 0) for e in evals), 3),
        },
        "steps": [
            {"seq": s["seq"], "actor": s["actor"], "action": s["action"], "status": s["status"], "purpose": s["purpose"],
             "expected_result": s["expected_result"], "verification": s["verification"], "hypothesis": s["hypothesis"],
             "params": json.loads(s["params_json"]), "result": json.loads(s["result_json"]),
             "next_decision": s["next_decision"], "candidate_id": s["candidate_id"], "evaluation_id": s["evaluation_id"],
             "model_call_id": s["model_call_id"], "tool_call_id": s["tool_call_id"],
             "started_at": s["started_at"], "ended_at": s["ended_at"]}
            for s in steps
        ],
        "config": {k: v for k, v in cfg.items() if k != "environment"},
        "environment": cfg.get("environment"),
        "reproduce": {
            "run_again": _run_command(run, cfg),
            "recheck_best": (shlex.join(["uv", "run", "routeevo", "check", run["task_id"],
                             next(c["code_path"] for c in cand_out if c["candidate_id"] == best_id),
                             "--dataset", "final", *_measure_args(cfg)])
                             if best_id else None),
            "report": f"uv run routeevo report {run_id}",
        },
        "started_at": run["started_at"], "loop_ended_at": run["loop_ended_at"], "ended_at": run["ended_at"],
    }
    out["research"] = research.summarize(out)
    out["progress"] = []
    for step in out["steps"]:
        if "progress" in step["result"]:
            item = dict(step["result"]["progress"])
            item["usage"] = _ledger([c for c in calls if c["ended_at"] <= step["ended_at"]])
            out["progress"].append(item)
    return out


def _measure_args(cfg: dict) -> list[str]:
    argv = []
    if cfg.get("measure", {}).get("cpuset_cpus") is not None:
        argv += ["--cpuset-cpus", cfg["measure"]["cpuset_cpus"]]
    if cfg.get("measure", {}).get("function_warmups", 1) != 1:
        argv += ["--function-warmups", str(cfg["measure"]["function_warmups"])]
    return argv


def _run_command(run, cfg: dict) -> str:
    argv = ["uv", "run", "routeevo", "run", run["task_id"], "--mode", run["mode"], "--snapshot", run["snapshot_id"]]
    protocol = cfg.get("research_protocol", {})
    if protocol.get("mode"):
        argv += ["--research-mode", protocol["mode"]]
    if protocol.get("fixed_model"):
        argv += ["--fixed-model", protocol["fixed_model"]]
    if protocol.get("final_evaluation") is False:
        argv += ["--dev-only"]
    argv += _measure_args(cfg)
    for flag, key in (("--wall-clock", "wall_clock_s"), ("--max-requests", "max_model_requests"),
                      ("--max-candidates", "max_candidates"), ("--request-timeout", "model_request_timeout_s")):
        argv += [flag, str(cfg["limits"][key])]
    return shlex.join(argv)


def _summary(run, best_id: str | None, final: dict | None, goal_met: bool) -> str:
    if run["status"] == "running":
        return "运行中"
    if not best_id:
        return f"没有有效产物（{run['stop_reason']}）"
    if final is None:
        return f"未执行最终测试（{run['stop_reason']}）；最佳候选 {best_id} 仅有开发验证结果"
    if not final["correct"]:
        return f"最终测试失败：{best_id} 在最终数据上 {final['status']}"
    if final.get("objective"):
        score = final["objective"]
        return f"最终方案 {best_id} 可行，原始得分 {score['value']}（{score['direction']}；基线 {score['baseline']}）"
    if best_id == "c0":
        return "无改进：保留初始程序，最终测试正确"
    if goal_met:
        return f"达到目标：{best_id} 最终测试正确，加速比 {final['speedup']}"
    return f"有产物但未达标：{best_id} 最终测试正确，加速比 {final['speedup']}"
