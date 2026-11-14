"""Export and audit the frozen 15-slot ALE batch from a local, consistent snapshot.

Run once after synchronization:
  PYTHONPATH=backend/src python docs/research/native-formal-20261114/export_ale.py --root SNAPSHOT_ROOT

Only this script's output directory is written. SQLite is opened read-only; task inputs,
databases and environment files are never exported. Missing/failed slots stay in the report.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "backend/src"))

from quotacrux.research_compare import comparable, summarize  # noqa: E402
from quotacrux.research_views import comparison_summary, estimate_cost, validate_pricing  # noqa: E402

CODE_SHA = "990f598b87f7c93bd27b6ceef5751bbc2d39dd79"
PLAN_ID = "research-ale-formal-20261114-v2"
KEYS = ("seq", "task_id", "repeat", "mode")
PROTOCOL_ERRORS = {"not_json", "unknown_action", "bad_field", "missing_field", "missing_code",
                   "code_too_large", "unknown_candidate", "unavailable_tool", "unknown_tool",
                   "candidate_budget", "independent_action", "independent_parent", "route_mismatch"}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def logical_sha(value):
    return sha(json.dumps(value, sort_keys=True).encode())


def need(condition, errors, message):
    if not condition:
        errors.append(message)


def copy_bytes(source, destination, errors, expected=None):
    if not source.is_file():
        errors.append(f"missing artifact: {source}")
        return None
    content = source.read_bytes()
    digest = sha(content)
    need(expected is None or expected == digest, errors, f"SHA256 mismatch: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    need(sha(destination.read_bytes()) == digest, errors, f"export SHA256 mismatch: {destination}")
    return digest


def rows(conn, table, run_id, order):
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE run_id=? ORDER BY {order}", (run_id,))]


def seconds(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() if a and b else None


def call_number(value):
    return int(value.rsplit("/", 1)[-1].removeprefix("m"))


def ledger(calls):
    result = {"requests": len(calls), "ok": sum(c["status"] == "ok" for c in calls),
              "errors": dict(Counter(c["error_kind"] for c in calls if c["error_kind"])),
              "latency_s": round(sum(c["latency_s"] or 0 for c in calls), 3)}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
        values = [c[key] for c in calls if c["usage_source"] != "not_applicable"]
        known = [x for x in values if x is not None]
        result[key] = sum(known) if known else (0 if not calls else None)
        result[f"{key}_unknown_calls"] = sum(x is None for x in values)
    return result


def token_total(usage):
    if any(usage.get(k) is None or usage.get(f"{k}_unknown_calls", 0)
           for k in ("input_tokens", "output_tokens")):
        return None
    return usage["input_tokens"] + usage["output_tokens"]


def assemble_continuation(root, target, frozen, initial, errors):
    directory = root / "formal-v2-continuation1"
    if not directory.exists():
        return initial
    manifest_path = directory / "frozen-manifest.json"
    manifest = read(manifest_path)
    source_path = directory / f"{manifest['plan_id']}.json"
    continuation = read(source_path)
    need(manifest == read(HERE / "ale-continuation-1.json"), errors, "continuation manifest differs from committed plan")
    changed = {k for k in frozen.keys() | manifest.keys() if frozen.get(k) != manifest.get(k)}
    need(changed == {"plan_id", "ale_plan", "continuation"}, errors, "continuation changes frozen execution conditions")
    need(continuation["status"] != "running", errors, "continuation snapshot is still running")
    need(continuation["plan"] == manifest["ale_plan"], errors, "continuation order differs from freeze")
    need(continuation["code_sha"] == frozen["code_sha"] and continuation["price_snapshot"] == frozen["pricing"],
         errors, "continuation code or prices differ")
    merged = deepcopy(initial)
    originals = {r["seq"]: r for r in merged["runs"]}
    need({r["seq"] for r in continuation["runs"]} == {r["seq"] for r in manifest["ale_plan"]},
         errors, "continuation slots differ from its plan")
    for row in continuation["runs"]:
        original = originals[row["seq"]]
        if original.get("run_id") or original["status"] != "not_run":
            errors.append(f"continuation attempts to replace an existing run: {row['seq']}")
            continue
        original.update(row)
    copy_bytes(source_path, target / "source-comparison-continuation1.json", errors)
    copy_bytes(manifest_path, target / "continuation-manifest.json", errors)
    merged["execution_segments"] = [
        {"comparison_id": source["comparison_id"], "status": source["status"],
         "created_at": source["created_at"], "ended_at": source.get("ended_at"),
         "batch_wall_clock_s": source.get("batch_wall_clock_s")}
        for source in (initial, continuation)]
    merged["ended_at"] = continuation.get("ended_at")
    merged["batch_wall_clock_s"] = seconds(merged["created_at"], merged["ended_at"])
    merged["active_batch_wall_clock_s"] = sum(s["batch_wall_clock_s"] for s in merged["execution_segments"])
    merged["interruption_gap_s"] = merged["batch_wall_clock_s"] - merged["active_batch_wall_clock_s"]
    merged["waves"] += continuation["waves"]
    states = {r["status"] for r in merged["runs"]}
    merged["status"] = "interrupted" if states & {"not_run", "running", "interrupted"} else (
        "completed" if states == {"completed"} else "failed")
    merged["assembly"] = {"method": "Fill only unopened original slots; preserve all previously started runs.",
                          "initial_artifact": "source-comparison-initial.json",
                          "continuation_artifact": "source-comparison-continuation1.json",
                          "continuation_source_sha256": sha(source_path.read_bytes())}
    summarize(merged)
    merged.pop("cost", None)
    merged["cost"] = comparison_summary(merged)["cost"]
    return merged


def hidden_input(text, number, mode, candidates, code, steps, errors, label):
    """Check generated structures against their provenance, not words in model-authored code."""
    header = "## Candidates (c0 is the initial program; actual best is withheld)\n"
    need(header in text, errors, f"{label}: hidden-best candidate heading missing")
    if header not in text:
        return
    tail = text.split(header, 1)[1].lstrip("\n")
    visible = [c for c in candidates if c["origin"] == "initial" or
               (mode == "no_feedback" and c["model_call_id"] and call_number(c["model_call_id"]) < number)]
    initial_step = next(s for s in steps if s["actor"] == "program" and s["action"] == "run_validation"
                        and s["candidate_id"] == "c0")
    initial = {**json.loads(initial_step["result_json"]), "speedup": None,
               "note": "initial program; measured score"}
    decoder = json.JSONDecoder()
    for candidate in visible:
        cid = candidate["candidate_id"]
        prefix = f"### {cid}\n"
        if not tail.startswith(prefix):
            errors.append(f"{label}: candidate list/order differs at {cid}")
            return
        head, end = decoder.raw_decode(tail[len(prefix):])
        expected = {k: candidate[k] for k in ("candidate_id", "origin", "parent_candidate_id")}
        if cid == "c0":
            expected["latest_evaluation"] = initial
        need(head == expected, errors, f"{label}: candidate {cid} metadata or frozen c0 feedback differs")
        tail = tail[len(prefix) + end:]
        block = f"\n```python\n{code[cid]}\n```"
        if not tail.startswith(block):
            errors.append(f"{label}: candidate {cid} code differs from submitted bytes")
            return
        tail = tail[len(block):].lstrip("\n")
    public_memory = "## Experience records from snapshot v0\nnone\n"
    if not tail.startswith(public_memory):
        errors.append(f"{label}: extra candidate/evidence or nonempty experience section")
        return
    tail = tail[len(public_memory):].lstrip("\n")
    budget_marker = "## Budget\n"
    if budget_marker not in tail:
        errors.append(f"{label}: Budget missing")
        return
    before, encoded = tail.rsplit(budget_marker, 1)
    budget, end = decoder.raw_decode(encoded)
    need(encoded[end:].strip() == "Reply with one JSON object for the next action.", errors,
         f"{label}: unexpected text after Budget")
    for key in ("best_candidate_id", "best_dev_speedup", "best_objective"):
        need(key in budget and budget[key] is None, errors, f"{label}: {key} not withheld")
    need(budget.get("best_result_visibility") == "withheld", errors, f"{label}: best visibility differs")
    need(budget.get("research_mode") == mode and budget.get("model_requests_used") == number - 1,
         errors, f"{label}: mode/request budget differs")
    expected_count = sum(c["origin"] == "model" and call_number(c["model_call_id"]) < number for c in candidates)
    need(budget.get("candidates_used") == expected_count, errors, f"{label}: candidate budget differs")
    allowed_budget = {"model_requests_used", "model_requests_max", "candidates_used", "candidates_max",
                      "wall_clock_elapsed_s", "wall_clock_limit_s", "current_model_role", "upgraded_to_large_model",
                      "best_candidate_id", "best_dev_speedup", "best_objective", "research_mode",
                      "best_result_visibility", "routed_to", "target_speedup", "task_target_speedup"}
    need(set(budget) == allowed_budget, errors, f"{label}: unexpected Budget fields")
    need(budget.get("target_speedup") is None and budget.get("task_target_speedup") is None and
         budget.get("upgraded_to_large_model") is False, errors, f"{label}: unexpected ALE target/model state")
    feedback_marker = "## Feedback on your previous reply\n"
    if feedback_marker in before:
        before, feedback_text = before.rsplit(feedback_marker, 1)
        feedback = json.loads(feedback_text.strip())
        need(set(feedback) <= {"problem", "kind", "message", "hint"}, errors, f"{label}: feedback result fields")
        need(feedback.get("problem") in {"invalid_action", "bad_response", "not_json", "empty_response", "truncated"},
             errors, f"{label}: external feedback exposed")
        if feedback.get("problem") == "invalid_action":
            need(feedback.get("kind") in PROTOCOL_ERRORS, errors, f"{label}: candidate evaluation exposed as protocol error")
    if mode == "independent":
        need(not before.strip() and feedback_marker not in tail, errors, f"{label}: independent history/feedback exposed")
        return
    expected_history = []
    for step in steps:
        if step["actor"] != "model" or not step["model_call_id"] or call_number(step["model_call_id"]) >= number:
            continue
        item = {"request": call_number(step["model_call_id"]), "action": step["action"], "purpose": step["purpose"],
                "expected_result": step["expected_result"], "verification": step["verification"],
                "hypothesis": step["hypothesis"], "params": json.loads(step["params_json"]),
                "candidate_id": step["candidate_id"]}
        if step["status"] == "invalid_action":
            item["protocol_error"] = json.loads(step["result_json"])
            need(item["protocol_error"].get("kind") in PROTOCOL_ERRORS, errors,
                 f"{label}: result-dependent history error")
        expected_history.append(item)
    before = before.strip()
    actual_history = []
    if before:
        marker = "## Steps so far\n"
        if not before.startswith(marker):
            errors.append(f"{label}: unexpected section before Budget")
            return
        actual_history = [json.loads(line) for line in before[len(marker):].splitlines() if line.strip()]
    need(actual_history == expected_history, errors, f"{label}: history differs from model-authored actions")


def audit_run(root, target, slot, frozen, conn):
    run_id = slot["run_id"]
    errors = []
    binding = frozen["workers"][slot["worker"]]
    source = root / f"var-worker-{slot['worker']}" / "runs" / run_id
    destination = target / run_id
    run_rows = rows(conn, "runs", run_id, "started_at")
    if len(run_rows) != 1:
        raise ValueError(f"expected one SQLite run: {run_id}")
    run = run_rows[0]
    cfg = json.loads(run["config_json"])
    candidates = rows(conn, "candidates", run_id, "seq")
    calls = rows(conn, "model_calls", run_id, "started_at, call_id")
    calls.sort(key=lambda c: call_number(c["call_id"]))
    steps = rows(conn, "steps", run_id, "seq")
    events = rows(conn, "events", run_id, "event_id")
    evaluations = rows(conn, "evaluations", run_id, "started_at, rowid")
    task_manifest = json.loads(conn.execute("SELECT manifest_json FROM tasks WHERE task_id=?", (slot["task_id"],)).fetchone()[0])
    for event in events:
        event["payload"] = json.loads(event.pop("payload_json"))
    report_path = source / "report.json"
    if report_path.is_file():
        report = read(report_path)
        copy_bytes(report_path, destination / "report.json", errors)
    else:
        errors.append("source report.json missing; exported partial DB record")
        report = {"run_id": run_id, "status": run["status"], "source_report_missing": True,
                  "config": {k: v for k, v in cfg.items() if k != "environment"},
                  "candidates": candidates, "stop_reason": run["stop_reason"]}
        write(destination / "report.json", report)
    need(run["task_id"] == slot["task_id"] and run["mode"] == "eval" and run["snapshot_id"] == "v0",
         errors, "task/eval/v0 differs from plan")
    need(cfg.get("research_protocol") == {"mode": slot["mode"], "fixed_model": "small", "final_evaluation": True},
         errors, "research mode/final policy differs")
    for key, expected in (("limits", frozen["limits"]), ("measure", binding["measure"]),
                          ("task_manifest_sha256", binding["manifest_sha256"]),
                          ("environment", binding["environment"]), ("action_schema_sha256", frozen["action_schema_sha256"]),
                          ("sandbox_image_id", binding["environment"]["image_id"])):
        need(cfg.get(key) == expected, errors, f"frozen configuration differs: {key}")
    expected_prompt = {"version": frozen["prompt_version"], "system_sha256": binding["prompt_sha256"][slot["mode"]]}
    need(cfg.get("prompt") == expected_prompt, errors, "prompt differs from freeze")
    need(cfg["models"]["small"] == frozen["model"] and not cfg.get("scripted"), errors, "model configuration differs")
    need(run["config_fingerprint"] == cfg["fingerprint"], errors, "DB configuration fingerprint differs")
    if not report.get("source_report_missing"):
        need(report["config"] == {k: v for k, v in cfg.items() if k != "environment"}, errors, "report/DB config differs")
        need(report["environment"] == cfg["environment"], errors, "report/DB environment differs")
        need(report["run_id"] == run_id and report["task"]["task_id"] == slot["task_id"], errors, "report identity differs")
        need(report["research_mode"] == slot["mode"], errors, "report research mode differs")
        need((report.get("best_candidate") or {}).get("candidate_id") == run["best_candidate_id"],
             errors, "report/DB selected candidate differs")
        need(slot.get("comparison_config") == comparable(report), errors, "central/report comparison config differs")
        need(slot.get("final_evaluation") == report["final_evaluation"], errors, "central/report final result differs")
        need(slot.get("final_status") == report["outcome"]["final_status"], errors, "central/report final status differs")
        need(slot.get("best_candidate_id") == (report.get("best_candidate") or {}).get("candidate_id"),
             errors, "central/report selected candidate differs")
    hashes, code = {}, {}
    need({p.name for p in (source / "candidates").glob("*.py")} == {f"{c['candidate_id']}.py" for c in candidates},
         errors, "candidate file/DB inventory differs")
    reported = {c["candidate_id"]: c for c in report.get("candidates", [])}
    for candidate in candidates:
        cid = candidate["candidate_id"]
        path = source / "candidates" / f"{cid}.py"
        hashes[cid] = copy_bytes(path, destination / "candidates" / path.name, errors, candidate["code_sha256"])
        if path.is_file():
            code[cid] = path.read_text()
        need(reported.get(cid, {}).get("code_sha256") == candidate["code_sha256"], errors, f"report/DB candidate SHA differs: {cid}")
    expected_call_files = {f"{c['call_id'].rsplit('/', 1)[-1]}.json" for c in calls}
    need({p.name for p in (source / "calls").glob("*.json")} == expected_call_files, errors, "model call inventory differs")
    hidden_checked = 0
    for call in calls:
        name = call["call_id"].rsplit("/", 1)[-1]
        path = source / "calls" / f"{name}.json"
        copy_bytes(path, destination / "model_calls" / path.name, errors)
        if not path.is_file():
            continue
        raw = read(path)
        request = raw["request"]
        model = frozen["model"]
        need(call["provider"] == model["provider"] and call["role"] == "small" and
             call["model_requested"] == model["model"], errors, f"{name}: actual call model/role differs")
        need(call["model_returned"] in (None, model["model"]), errors, f"{name}: provider returned a different model")
        expected_request = {"model": model["model"], "max_tokens": model["max_output_tokens"], "stream": False,
                            "enable_thinking": model["enable_thinking"], "response_format": {"type": model["response_format"]}}
        for key in ("reasoning_effort", "temperature"):
            if model[key] is not None:
                expected_request[key] = model[key]
        need({k: v for k, v in request.items() if k != "messages"} == expected_request,
             errors, f"{name}: actual request parameters differ")
        messages = request["messages"]
        need([m["role"] for m in messages] == ["system", "user"], errors, f"{name}: message roles differ")
        need(sha(messages[0]["content"].encode()) == expected_prompt["system_sha256"] == raw["system_prompt_sha256"],
             errors, f"{name}: actual system prompt hash differs")
        if slot["mode"] in ("no_feedback", "independent"):
            hidden_input(messages[1]["content"], call_number(call["call_id"]), slot["mode"], candidates, code,
                         steps, errors, name)
            hidden_checked += 1
    need(len(calls) <= frozen["limits"]["max_model_requests"], errors, "request budget exceeded")
    need(sum(c["origin"] == "model" for c in candidates) <= frozen["limits"]["max_candidates"], errors, "candidate budget exceeded")
    loops = [e for e in events if e["type"] == "loop_ended"]
    finals = [e for e in events if e["type"] == "final_eval_started"]
    best = run["best_candidate_id"]
    if run["status"] not in ("running", "interrupted"):
        need(len(loops) == 1, errors, "missing/nonunique loop freeze event")
    if loops:
        loop = loops[0]
        need(loop["payload"]["best_candidate_id"] == best, errors, "best changed after loop freeze")
        need(all(e["event_id"] < loop["event_id"] for e in events if e["type"] in ("model_started", "model_finished", "candidate_created")),
             errors, "model call/candidate creation after loop freeze")
        need(all(c["ended_at"] and c["ended_at"] <= loop["ts"] for c in calls), errors, "model call ended after loop freeze")
        need(all(e["event_id"] > loop["event_id"] and e["payload"]["candidate_id"] == best for e in finals),
             errors, "final started before freeze or with another candidate")
    final = next((e for e in evaluations if e["evaluation_id"] == run["final_evaluation_id"]), None)
    for ev in evaluations:
        detail = json.loads(ev["detail_json"])
        need(ev["task_id"] == slot["task_id"] and
             ev["dataset_sha256"] == task_manifest["files"][f"{ev['dataset']}_input"]["sha256"],
             errors, f"evaluation task/dataset hash differs: {ev['evaluation_id']}")
        if ev["evaluator_version"] != "static-check":
            need(detail["candidate_sha256"] == hashes.get(ev["candidate_id"]), errors,
                 f"evaluation candidate SHA differs: {ev['evaluation_id']}")
        if ev["dataset"] == "final":
            need(bool(loops) and ev["started_at"] >= loops[0]["ts"], errors, "final data evaluated before loop freeze")
    if best and best != "c0":
        selected_dev = [e for e in evaluations if e["candidate_id"] == best and e["dataset"] == "dev"]
        need(bool(selected_dev) and selected_dev[-1]["status"] == "passed" and
             json.loads(selected_dev[-1]["detail_json"]).get("eligible_for_selection", True),
             errors, "selected candidate lacks an eligible passed development evaluation")
    if final:
        need(final["candidate_id"] == best and bool(finals), errors, "final candidate differs from frozen best")
        if not report.get("source_report_missing"):
            need(report["best_candidate"]["candidate_id"] == best == report["final_evaluation"]["candidate_id"],
                 errors, "report best/final candidate differs")
            need(report["final_evaluation"]["evaluation_id"] == final["evaluation_id"], errors, "report final evaluation differs")
    if best in code:
        copy_bytes(source / "candidates" / f"{best}.py", destination / "best.py", errors, hashes[best])
    usage = ledger(calls)
    if not report.get("source_report_missing"):
        for key in ("requests", "input_tokens", "output_tokens", "input_tokens_unknown_calls", "output_tokens_unknown_calls"):
            need(report["usage"]["total"].get(key) == usage[key], errors, f"report/DB usage differs: {key}")
        need(report["iterations"]["model_requests"] == len(calls), errors, "report request count differs")
    audit = {"passed": not errors, "errors": errors, "candidate_sha256": hashes,
             "model_calls_exported": len(calls), "hidden_input_requests_checked": hidden_checked,
             "loop_freeze_events": loops, "final_start_events": finals,
             "evaluation_count": len(evaluations), "actual_usage": usage,
             "model_call_records": calls, "timing_side_channel": "total wall-clock budget is intentionally visible"}
    write(destination / "audit.json", audit)
    return report, audit, evaluations


def curve_points(report, evaluations, pricing):
    points = []
    initial = next((e for e in evaluations if e["dataset"] == "dev" and e["candidate_id"] == "c0"), None)
    if initial:
        value = json.loads(initial["detail_json"]).get("objective", {}).get("value")
        if value is not None:
            points.append({"source": "measured_initial_dev", "elapsed_s": seconds(report.get("started_at"), initial["ended_at"]),
                           "tokens": 0, "cny": 0, "value": value, "candidate_id": "c0"})
    for point in report.get("progress", []):
        cost = estimate_cost(point["usage"], pricing)
        points.append({"source": "recorded_progress", "elapsed_s": point["elapsed_s"],
                       "tokens": token_total(point["usage"]), "cny": cost["amount"],
                       "value": point["value"], "candidate_id": point["best_candidate_id"]})
    if points and report.get("loop_ended_at"):
        usage = report["usage"]["total"]
        points.append({**points[-1], "source": "carry_forward_at_loop_freeze",
                       "elapsed_s": report["timing"]["agent_loop_s"], "tokens": token_total(usage),
                       "cny": estimate_cost(usage, pricing)["amount"]})
    return points


def plot_curves(target, curves):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {"status": "dependency_missing", "reason": "matplotlib unavailable; curves.json retains all plotting data", "files": []}
    files = []
    colors = {"feedback": "#087F8C", "independent": "#D26A20", "no_feedback": "#7B4AB5"}
    axes = (("elapsed_s", "Research elapsed time (s)", "wall-clock"),
            ("tokens", "Cumulative input + output tokens", "tokens"), ("cny", "Estimated API cost (CNY)", "cny"))
    for problem in sorted({r["problem"] for r in curves}):
        for axis, label, suffix in axes:
            fig, ax = plt.subplots(figsize=(9, 5.3), layout="constrained")
            for run in [r for r in curves if r["problem"] == problem]:
                points = [p for p in run["points"] if p.get(axis) is not None and p.get("value") is not None]
                if not points:
                    continue
                ax.step([p[axis] for p in points], [p["value"] for p in points], where="post",
                        label=f"{run['mode']} r{run['repeat']}", color=colors[run["mode"]],
                        linestyle=("-", "--", ":")[run["repeat"] - 1], linewidth=1.7)
            ax.set(title=f"{problem}: retained development score", xlabel=label, ylabel="Raw score (5 dev cases; higher is better)")
            ax.grid(alpha=0.2)
            if ax.lines:
                ax.legend(fontsize=8, ncols=2)
            path = target / f"{problem}-{suffix}.svg"
            fig.savefig(path, format="svg", metadata={"Date": None})
            fig.savefig(path.with_suffix(".png"), dpi=160)
            plt.close(fig)
            files.append(path.name)
    return {"status": "completed", "files": files, "png_files": [name.removesuffix('.svg') + '.png' for name in files]}


def fmt(value, digits=3):
    if value is None:
        return "—"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def markdown(summary):
    totals = summary["totals"]
    cost_text = (f"CNY {fmt(totals['estimated_cny'], 6)}" if totals["estimated_cny"] is not None else
                 f"总额未知，已报告用量部分 CNY {fmt(totals['estimated_cny_known_subtotal'], 6)}")
    lines = ["# ALE 正式评测结果", "",
             f"源码 `{summary['code_sha']}`；计划 `{summary['plan_id']}`；固定 Qwen3.8-27B、eval/v0。",
             "每轮上限 900 秒 / 20 请求 / 10 候选；每题 5 dev / 15 final。final 在开发选优冻结后执行，不回流模型。", "",
             f"15 个计划位置全部保留；已启动 {totals['started']}，final 通过 {totals['final_correct']}，"
             f"未运行 {totals['not_run']}。审计 {'通过' if summary['audit']['passed'] else '发现问题，见 summary.json 的 audit'}。",
             f"研究运行状态：{json.dumps(totals['status_counts'], ensure_ascii=False)}；研究终止状态与 final 验收分别记录。",
             f"批次墙钟 {fmt(summary['batch_wall_clock_s'])} 秒；累计 episode 墙钟 {fmt(totals['wall_clock_s'])} 秒；"
             f"请求 {totals['requests']} 次；输入 Token {fmt(totals['input_tokens'])}，输出 Token {fmt(totals['output_tokens'])}；"
             f"冻结标价估算：{cost_text}。", "",
             f"累计模型等待 {fmt(totals['model_wait_s'])} 秒，开发评测 {fmt(totals['dev_evaluation_s'])} 秒，"
             f"最终评测 {fmt(totals['final_evaluation_s'])} 秒。API 错误计数：{json.dumps(totals['api_errors'], ensure_ascii=False)}。", "",
             "| 题目 | 模式 | final 通过/计划 | final 原始分数（各重复） | c0 基线差值（各重复） | c0交付 | 候选通过/提出 | CNY |",
             "|---|---|---:|---|---|---:|---:|---:|"]
    for group in summary["groups"]:
        lines.append(f"| {group['problem']} | {group['mode']} | {group['final_correct']}/{group['planned']} | "
                     f"{', '.join(fmt(x) for x in group['final_scores'])} | {', '.join(fmt(x) for x in group['final_deltas'])} | "
                     f"{group['c0_deliveries']} | {group['candidates_passed']}/{group['candidates_proposed']} | {fmt(group['estimated_cny'], 6)} |")
    lines += ["", "| 序号 | 题目 / 重复 / 模式 | 状态 / final | best | final / c0 | 差值 | 请求 | episode秒 |",
              "|---:|---|---|---|---|---:|---:|---:|"]
    for row in summary["runs"]:
        best = row.get("best_candidate_id") or "—"
        if row.get("run_id"):
            best = f"[{best}]({row['run_id']}/report.json)"
        lines.append(f"| {row['seq']} | {row['problem']} / r{row['repeat']} / {row['mode']} | "
                     f"{row['status']} / {row['final_status']} | {best} | {fmt(row.get('final_score'))} / {fmt(row.get('final_baseline'))} | "
                     f"{fmt(row.get('final_delta'))} | {fmt(row.get('usage', {}).get('requests'))} | {fmt(row.get('timing', {}).get('wall_clock_total_s'))} |")
    lines += ["", "得分是各题原生裁判分数之和。final 失败或缺失时分数为 null，保留在计划分母；"
              "研究因接口错误终止但冻结候选通过 final 的，保留真实得分和 failed 运行状态。c0 为零时百分比为 null。"
              "三次重复报告差值及波动，不据此宣称统计显著。费用沿用冻结输入/输出费率，缓存按普通输入价估算；未知用量保持 null。",
              "", "过程曲线使用开发集已保留候选的真实 progress；初始点来自 c0 开发评测，末点仅将最后保留值延续至研究结束。"
              "曲线不含 final 得分，不将批次并行节省的墙钟解释为算法加速。"]
    if summary.get("execution_segments"):
        lines += ["", "第 10 个位置因 AIPing HTTP 400 终止，原始失败记录保留。续批仅执行此前未启动的 11–15，"
                  "沿用原源码、参数和顺序。comparison.json 是两段原始比较文件的派生合并，原文件另存 source-comparison-*.json。",
                  f"两段执行墙钟合计 {fmt(summary['active_batch_wall_clock_s'])} 秒；"
                  f"中断间隔 {fmt(summary['interruption_gap_s'])} 秒，计入上述整体批次墙钟。"]
    for filename in summary["plots"]["files"]:
        lines += ["", f"![{filename.removesuffix('.svg')}]({filename})"]
    if summary["plots"]["status"] != "completed":
        lines += ["", "当前环境未安装 matplotlib；绘图数据已保存在 curves.json，可在具备 matplotlib 的环境生成。"]
    lines += ["", "候选、原始请求/响应 JSON 逐字节复制，SHA256 见 SHA256SUMS 和各 run 的 audit.json。"
              "无反馈核验只比对生成的候选元数据、预算及模型历史来源；模型自身分析中的得分讨论不作为泄漏证据。"
              "总墙钟预算是协议允许的时间信号。", "", "复现导出：", "", "```sh",
              "PYTHONPATH=backend/src python docs/research/native-formal-20261114/export_ale.py --root /path/to/snapshot --output /path/to/new-results",
              "```", "", "各轮原始执行命令保存在对应 report.json 的 reproduce 中；复现真实研究会产生新请求和新费用。", ""]
    return "\n".join(lines)


def aggregate(records):
    started = [r for r in records if r.get("run_id")]
    usage_rows = [r["usage"] for r in started if r.get("usage") is not None]
    result = {"planned": len(records), "started": len(started), "not_run": sum(r["status"] == "not_run" for r in records),
              "status_counts": dict(Counter(r["status"] for r in records)),
              "final_status_counts": dict(Counter(r["final_status"] for r in records)),
              "final_correct": sum(r.get("final_correct") is True for r in records),
              "c0_deliveries": sum(r.get("best_candidate_id") == "c0" for r in records),
              "candidates_proposed": sum(r.get("iterations", {}).get("candidates_proposed", 0) for r in records),
              "candidates_passed": sum(r.get("iterations", {}).get("candidates_passed", 0) for r in records),
              "requests": sum(u["requests"] for u in usage_rows),
              "api_errors": dict(sum((Counter(u.get("errors", {})) for u in usage_rows), Counter())),
              "missing_usage_runs": len(started) - len(usage_rows)}
    for key in ("input_tokens", "output_tokens"):
        values = [u[key] for u in usage_rows]
        unknown = sum(u[f"{key}_unknown_calls"] for u in usage_rows)
        result[key] = sum(values) if all(v is not None for v in values) and not unknown and len(usage_rows) == len(started) else None
        result[f"{key}_known_subtotal"] = sum(v for v in values if v is not None)
        result[f"{key}_unknown_calls"] = unknown
    costs = [r.get("estimated_cny") for r in started]
    result["estimated_cny"] = sum(costs) if all(v is not None for v in costs) else None
    result["estimated_cny_known_subtotal"] = sum(r.get("known_estimated_cny", r.get("estimated_cny")) or 0
                                                  for r in started)
    for key in ("wall_clock_total_s", "model_wait_s", "dev_evaluation_s", "final_evaluation_s"):
        values = [r.get("timing", {}).get(key) for r in started]
        name = "wall_clock_s" if key == "wall_clock_total_s" else key
        result[name] = sum(v for v in values if v is not None)
        result[f"{name}_missing_runs"] = sum(v is None for v in values)
    proposed = result["candidates_proposed"]
    result["candidate_pass_rate"] = result["candidates_passed"] / proposed if proposed else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "ale/results")
    args = parser.parse_args()
    root, target = args.root.resolve(), args.output.resolve()
    if target.exists() and any(target.iterdir()):
        raise RuntimeError("output must be empty; preserve the previous export")
    batch = root / "formal-v2"
    frozen_path = batch / "frozen-manifest.json"
    if not frozen_path.is_file():
        frozen_path = root / "frozen-manifest.json"
    frozen = read(frozen_path)
    source_comparison = batch / f"{PLAN_ID}.json"
    comparison = read(source_comparison)
    errors = []
    need(frozen == read(HERE / "ale-freeze.json"), errors, "batch freeze differs from the committed ALE freeze")
    need(frozen["code_sha"] == CODE_SHA == comparison["code_sha"], errors, "source SHA differs from this frozen batch")
    need(frozen["plan_id"] == PLAN_ID == comparison["plan_id"], errors, "plan id differs")
    need(len(frozen["ale_plan"]) == 15 and comparison["plan"] == frozen["ale_plan"], errors, "15-slot plan differs")
    need(comparison["price_snapshot"] == frozen["pricing"], errors, "price snapshot differs")
    need(comparison["status"] != "running", errors, "batch snapshot is still running")
    validate_pricing(frozen["pricing"])
    need(frozen["pricing"]["currency"] == "CNY", errors, "price currency is not CNY")
    target.mkdir(parents=True, exist_ok=True)
    copy_bytes(source_comparison, target / "source-comparison-initial.json", errors)
    copy_bytes(frozen_path, target / "frozen-manifest.json", errors)
    comparison = assemble_continuation(root, target, frozen, comparison, errors)
    write(target / "comparison.json", comparison)
    keyed = {}
    for item in comparison["runs"]:
        key = tuple(item[k] for k in KEYS)
        need(key not in keyed, errors, f"duplicate central slot: {key}")
        keyed[key] = item
    expected_keys = {tuple(s[k] for k in KEYS) for s in frozen["ale_plan"]}
    need(set(keyed) <= expected_keys, errors, "unplanned central slots present")
    conns, task_audit = {}, {}
    try:
        for worker, binding in frozen["workers"].items():
            var = root / f"var-worker-{worker}"
            conn = sqlite3.connect(f"{(var / 'routeevo.sqlite3').as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            conns[worker] = conn
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (binding["task_id"],)).fetchone()
            if row is None:
                errors.append(f"worker {worker}: task is not registered in SQLite")
                continue
            manifest = json.loads(row["manifest_json"])
            need(logical_sha(manifest) == row["manifest_sha256"] == binding["manifest_sha256"], errors,
                 f"worker {worker}: task manifest hash differs")
            task_dir = var / "tasks" / binding["task_id"]
            need(read(task_dir / "manifest.json") == manifest, errors, f"worker {worker}: file/DB manifest differs")
            checked, absent = [], []
            for key, meta in manifest["files"].items():
                path = task_dir / meta["file"]
                if path.is_file():
                    need(sha(path.read_bytes()) == meta["sha256"], errors, f"worker {worker}: task file hash differs: {key}")
                    checked.append(key)
                else:
                    absent.append(key)
            task_audit[worker] = {"task_id": binding["task_id"], "manifest_sha256": row["manifest_sha256"],
                                  "files_verified_locally": checked, "files_not_synchronized": absent}
        output, curves, run_audits, seen = [], [], {}, set()
        for plan in frozen["ale_plan"]:
            key = tuple(plan[k] for k in KEYS)
            slot = keyed.get(key, dict(plan, status="not_run", final_status="not_run"))
            need(key in keyed, errors, f"central slot missing: {key}")
            need(all(slot.get(k) == v for k, v in plan.items()), errors, f"frozen slot metadata differs: {plan['seq']}")
            binding = frozen["workers"][plan["worker"]]
            result = {**plan, "problem": binding["problem"], "run_id": slot.get("run_id"),
                      "status": slot.get("status", "not_run"), "final_status": slot.get("final_status", "not_run"),
                      "stop_reason": slot.get("stop_reason"), "error": slot.get("error")}
            # Retain central observations even when a particular source artifact is incomplete.
            for field in ("iterations", "timing", "usage", "best_candidate_id"):
                if slot.get(field) is not None:
                    result[field] = deepcopy(slot[field])
            if result.get("usage") is not None:
                result["estimated_cny"] = estimate_cost(result["usage"], frozen["pricing"])["amount"]
            if slot.get("run_id"):
                run_id = slot["run_id"]
                need(run_id not in seen, errors, f"run reused by multiple slots: {run_id}")
                seen.add(run_id)
                try:
                    report, audit, evaluations = audit_run(root, target, slot, frozen, conns[plan["worker"]])
                    run_audits[run_id] = audit
                    errors.extend(f"{run_id}: {e}" for e in audit["errors"])
                    final = report.get("final_evaluation") or {}
                    correct = final.get("status") == "passed" and final.get("correct") is True
                    objective = final.get("objective") or {}
                    value, baseline = (objective.get("value"), objective.get("baseline")) if correct else (None, None)
                    delta = value - baseline if value is not None and baseline is not None else None
                    cost = estimate_cost(audit["actual_usage"], frozen["pricing"])
                    # A failed call can have unknown usage while earlier calls remain fully reported.
                    known_calls = [c for c in audit["model_call_records"]
                                   if c["input_tokens"] is not None and c["output_tokens"] is not None]
                    known_cost = estimate_cost(ledger(known_calls), frozen["pricing"])["amount"]
                    cost["known_amount"] = known_cost
                    result.update(best_candidate_id=(report.get("best_candidate") or {}).get("candidate_id"),
                        final_correct=correct, final_score=value, final_baseline=baseline, final_delta=delta,
                        final_relative_delta=delta / baseline if delta is not None and baseline else None,
                        final_observed_objective=objective or None, iterations=report.get("iterations", {}),
                        timing=report.get("timing", {}), usage=audit["actual_usage"], cost=cost,
                        estimated_cny=cost["amount"], known_estimated_cny=known_cost, audit_passed=audit["passed"])
                    curves.append({"run_id": run_id, "problem": binding["problem"], "task_id": plan["task_id"],
                                   "mode": plan["mode"], "repeat": plan["repeat"],
                                   "points": curve_points(report, evaluations, frozen["pricing"])})
                except (KeyError, ValueError, TypeError, OSError, sqlite3.Error) as exc:
                    message = f"{run_id}: incomplete artifact audit: {type(exc).__name__}: {exc}"
                    errors.append(message)
                    result.update(audit_passed=False, audit_error=message)
            output.append(result)
        groups = []
        for problem in sorted({r["problem"] for r in output}):
            for mode in ("feedback", "independent", "no_feedback"):
                selected = sorted((r for r in output if r["problem"] == problem and r["mode"] == mode), key=lambda r: r["repeat"])
                if not selected:
                    continue
                values = [r.get("final_score") for r in selected]
                usable = [x for x in values if x is not None]
                groups.append({"problem": problem, "mode": mode, **aggregate(selected), "final_scores": values,
                               "final_baselines": [r.get("final_baseline") for r in selected],
                               "final_deltas": [r.get("final_delta") for r in selected],
                               "final_median": statistics.median(usable) if usable else None})
        recalculated = summarize(deepcopy(comparison))
        need(recalculated["fair"] == comparison["fair"], errors, "stored fairness differs from recomputation")
        write(target / "curves.json", curves)
        plots = plot_curves(target, curves)
        summary = {"plan_id": PLAN_ID, "code_sha": frozen["code_sha"], "status": comparison["status"],
                   "fair": recalculated["fair"], "batch_wall_clock_s": comparison.get("batch_wall_clock_s"),
                   "execution_segments": comparison.get("execution_segments"),
                   "active_batch_wall_clock_s": comparison.get("active_batch_wall_clock_s"),
                   "interruption_gap_s": comparison.get("interruption_gap_s"),
                   "pricing": frozen["pricing"], "parallel_policy": frozen["parallel_policy"],
                   "judge_affinity": frozen["judge_affinity"], "runs": output, "groups": groups,
                   "pairs": recalculated["summary"]["pairs"], "totals": aggregate(output), "plots": plots,
                   "audit": {"passed": not errors, "errors": errors, "tasks": task_audit,
                             "started_runs_audited": len(run_audits),
                             "source_comparison_sha256": sha(source_comparison.read_bytes()),
                             "derived_comparison_sha256": sha((target / "comparison.json").read_bytes()),
                             "frozen_manifest_file_sha256": sha(frozen_path.read_bytes()),
                             "export_script_sha256": sha(Path(__file__).read_bytes()),
                             "source_verification": "frozen manifest and recorded configs; host clean-SHA check was performed by run_ale.py before each slot"}}
        write(target / "summary.json", summary)
        (target / "README.md").write_text(markdown(summary))
        checksums = [f"{sha(path.read_bytes())}  {path.relative_to(target)}" for path in sorted(target.rglob("*")) if path.is_file()]
        (target / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
        print(json.dumps({"output": str(target), "audit_passed": not errors, "audit_errors": errors,
                          "totals": summary["totals"], "plots": plots}, ensure_ascii=False, indent=2))
    finally:
        for conn in conns.values():
            conn.close()
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
