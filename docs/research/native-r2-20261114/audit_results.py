"""Summarize completed development pilots without exporting private model requests.

Run from any directory. Full request isolation/retention checks need the ignored
backend/var/runs files; missing raw calls are reported rather than treated as passes.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMPARISON = "research-20261114T053410-bfde.json"


def read(path: Path):
    return json.loads(path.read_text())


def action_from_call(call: dict) -> dict:
    response = call.get("response")
    if not isinstance(response, dict) or not response.get("choices"):
        return {}
    text = response["choices"][0].get("message", {}).get("content") or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match[1]
    if not text.startswith("{"):
        text = text[text.find("{"):text.rfind("}") + 1]
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def user_state(call: dict) -> str:
    return next(message["content"] for message in call["request"]["messages"] if message["role"] == "user")


def section(state: str, title: str) -> str:
    heading = f"## {title}\n"
    return state.split(heading, 1)[1].split("\n## ", 1)[0].strip() if heading in state else ""


def feedback_retention(steps: list[dict], calls: dict[int, dict]) -> dict:
    checks, missing, unavailable = [], [], []
    analyses = [step for step in steps if step["action"] == "analyze" and step["status"] == "done"]
    for step in analyses:
        fields = {}
        if step["result"].get("analysis"):
            fields["analysis"] = step["result"]["analysis"]
        if step.get("hypothesis"):
            fields["hypothesis"] = step["hypothesis"]
        if not fields:
            continue
        next_call = int(step["model_call_id"].rsplit("/m", 1)[1]) + 1
        if next_call not in calls:
            unavailable.append({"step": step["seq"], "next_call": next_call})
            continue
        history = section(user_state(calls[next_call]), "Steps so far")
        entries = [json.loads(line) for line in history.splitlines()] if history else []
        entry = next((item for item in entries if item["step"] == step["seq"]), {})
        absent = []
        if "analysis" in fields and (entry.get("result") or {}).get("analysis") != fields["analysis"]:
            absent.append("analysis")
        if "hypothesis" in fields and entry.get("hypothesis") != fields["hypothesis"]:
            absent.append("hypothesis")
        checks.append(step["seq"])
        if absent:
            missing.append({"step": step["seq"], "next_call": next_call, "fields": absent})
    return {"analyze_steps": len(analyses),
            "null_analysis_steps": sum(not step["result"].get("analysis") for step in analyses),
            "next_request_checks": len(checks), "retained_next_request_count": len(checks) - len(missing),
            "missing_fields": missing, "unavailable_next_requests": unavailable}


def independent_isolation(calls: dict[int, dict]) -> dict:
    bodies, violations, budgets = set(), [], []
    for number, call in sorted(calls.items()):
        state = user_state(call)
        bodies.add(hashlib.sha256(state.split("## Budget\n", 1)[0].encode()).hexdigest())
        checks = {
            "message_roles": [message["role"] for message in call["request"]["messages"]] == ["system", "user"],
            "only_c0": re.findall(r"^### (c\d+)\s*$", state, re.MULTILINE) == ["c0"],
            "no_history": not section(state, "Steps so far"),
            "no_previous_feedback": not section(state, "Feedback on your previous reply"),
            "no_evidence": not section(state, "Evidence collected in this run"),
            "empty_experience": section(state, "Experience records from snapshot v0") == "none",
        }
        budget = json.loads(section(state, "Budget").split("\nReply with", 1)[0])
        budgets.append(budget)
        checks["visible_best_c0"] = budget["best_candidate_id"] == "c0"
        for name, passed in checks.items():
            if not passed:
                violations.append({"call": number, "check": name})
    changing = [name for name in budgets[0]
                if len({json.dumps(budget[name], sort_keys=True) for budget in budgets}) > 1] if budgets else []
    return {"checked_calls": len(calls), "non_budget_body_versions": len(bodies),
            "changing_budget_fields": changing, "violations": violations}


def audit_run(report_path: Path, raw_runs: Path) -> dict:
    report = read(report_path)
    run_id = report["run_id"]
    mode = report["config"]["research_protocol"]["mode"]
    steps = [step for step in report["steps"] if step["model_call_id"]]
    calls = {int(path.stem[1:]): read(path) for path in (raw_runs / run_id / "calls").glob("m*.json")}
    invalid = [step for step in steps if step["status"] == "invalid_action"]
    invalid_actions, invalid_fields = Counter(), Counter()
    for step in invalid:
        number = int(step["model_call_id"].rsplit("/m", 1)[1])
        action = action_from_call(calls[number]) if number in calls else {}
        invalid_actions[action.get("action", "unavailable")] += 1
        for name in ("purpose", "expected_result", "verification"):
            if action:
                value = action.get(name)
                state = ("absent" if name not in action else "null" if value is None else
                         "empty" if isinstance(value, str) and not value.strip() else None)
                if state:
                    invalid_fields[f"{name}:{state}"] += 1
    candidates = [candidate for candidate in report["candidates"] if candidate["origin"] == "model"]
    groups, unavailable_code, invalid_code = defaultdict(list), [], []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        paths = [report_path.parent / "candidates" / f"{candidate_id}.py",
                 raw_runs / run_id / "candidates" / f"{candidate_id}.py", Path(candidate["code_path"])]
        source = next((path for path in paths if path.is_file()), None)
        if source is None:
            unavailable_code.append(candidate_id)
            continue
        try:
            tree = ast.dump(ast.parse(source.read_text()), include_attributes=False)
        except SyntaxError:
            invalid_code.append(candidate_id)
            continue
        groups[hashlib.sha256(tree.encode()).hexdigest()].append(candidate_id)
    requests = report["iterations"]["model_requests"]
    result = {
        "run_id": run_id, "task_id": report["task"]["task_id"], "family": report["task"]["family"], "mode": mode,
        "status": report["status"], "stop_reason": report["stop_reason"],
        "prompt_version": report["config"]["prompt"]["version"],
        "model_requests": requests, "recorded_actions": dict(Counter(step["action"] for step in steps)),
        "invalid_count": len(invalid), "invalid_types": dict(Counter(step["result"]["kind"] for step in invalid)),
        "invalid_intended_actions": dict(invalid_actions), "invalid_common_fields": dict(invalid_fields),
        "candidates_proposed": len(candidates), "candidates_passed": report["iterations"]["candidates_passed"],
        "candidates_per_request": len(candidates) / requests if requests else None,
        "unique_code_hashes": len({candidate["code_sha256"] for candidate in candidates}),
        "unique_ast_candidates": len(groups), "ast_duplicate_groups": [group for group in groups.values() if len(group) > 1],
        "unavailable_candidate_code": unavailable_code, "invalid_candidate_syntax": invalid_code,
        "raw_calls_available": len(calls), "raw_calls_complete": set(calls) == set(range(1, requests + 1)),
        "response_formats": dict(Counter(call["request"].get("response_format", {}).get("type", "omitted") for call in calls.values())),
        "wall_clock_total_s": report["timing"]["wall_clock_total_s"],
        "final_evaluation_disabled": report["config"]["research_protocol"]["final_evaluation"] is False,
        "final_evaluation_absent": report["final_evaluation"] is None,
    }
    result["feedback_retention" if mode == "feedback" else "independent_isolation"] = (
        feedback_retention(steps, calls) if mode == "feedback" else independent_isolation(calls))
    return result


def by_mode(runs: list[dict]) -> dict:
    result = {}
    for mode in ("feedback", "independent"):
        selected = [run for run in runs if run["mode"] == mode]
        totals = {name: sum(run[name] for run in selected) for name in
                  ("model_requests", "invalid_count", "candidates_proposed", "candidates_passed", "unique_ast_candidates")}
        for name in ("recorded_actions", "invalid_types", "invalid_intended_actions", "invalid_common_fields"):
            counts = Counter()
            for run in selected:
                counts.update(run[name])
            totals[name] = dict(counts)
        totals["candidates_per_request"] = totals["candidates_proposed"] / totals["model_requests"] if totals["model_requests"] else None
        result[mode] = totals
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, default=HERE / "comparison.json" if (HERE / "comparison.json").exists()
                        else ROOT / "backend/var/comparisons" / COMPARISON)
    parser.add_argument("--baseline", type=Path, default=HERE.parent / "native-20261114")
    parser.add_argument("--raw-runs", type=Path, default=ROOT / "backend/var/runs")
    parser.add_argument("--output", type=Path, default=HERE / "protocol-audit.json")
    args = parser.parse_args()
    comparison = read(args.comparison)
    if comparison["status"] != "completed" or len(comparison["runs"]) != 4:
        parser.error("the four-run development comparison must be completed before auditing")
    baseline = [audit_run(path, args.raw_runs) for path in sorted(args.baseline.glob("*/report.json"))]
    second = []
    for item in comparison["runs"]:
        exported = args.output.parent / item["run_id"] / "report.json"
        second.append(audit_run(exported if exported.exists() else args.raw_runs / item["run_id"] / "report.json", args.raw_runs))
    result = {"comparison_id": comparison["comparison_id"], "scope": "development pilot; no final evaluation",
              "rounds": {"first": {"runs": baseline, "by_mode": by_mode(baseline)},
                         "second": {"runs": second, "by_mode": by_mode(second)}},
              "all_second_round_final_evaluations_absent": all(run["final_evaluation_absent"] and run["final_evaluation_disabled"] for run in second)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "second_round_by_mode": result["rounds"]["second"]["by_mode"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
