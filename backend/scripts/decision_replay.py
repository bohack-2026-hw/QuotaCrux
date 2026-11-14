"""Build chronological A/B replay cases, run Decisions in shadow mode, and summarize measured labels.

No runner/database imports, candidate execution, hidden-final inputs, or experience publication.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics

from quotacrux.config import load_dotenv
from quotacrux.llm.openai_decisions import MODEL, PRICE_VERSION, decide, estimate_decision_cost

PROTOCOL = "decision-replay-v1"
THRESHOLD = 0.5
ROUTE_QUESTION = {
    "type": "choice", "name": "next_model",
    "instructions": "Choose which code-generating model should handle the next request. The goal is correct code "
    "meeting target speedup within the remaining budget. Weigh evidence of progress, failed approaches, tool "
    "evidence and task difficulty against extra large-model cost and latency. Qwen is the small model; GPT is "
    "the large model. Upgrade is irreversible. Do not merely repeat the current role or a fixed request-count rule.",
    "choices": [
        {"value": "small", "description": "Continue with Qwen for the next request."},
        {"value": "large", "description": "Upgrade now to the stronger, more expensive GPT model."},
    ],
}
CANDIDATE_QUESTIONS = [
    {"type": "predicate", "name": "correct", "instructions": "Would proposed_candidate satisfy the complete "
     "input/output contract for all valid inputs, including the public corner cases? Judge the code, not its "
     "author's confidence. No evaluation result for this candidate is available yet."},
    {"type": "predicate", "name": "on_target", "instructions": "Would proposed_candidate pass correctness and "
     "achieve the active target_speedup against the initial program on this dev workload, with every candidate "
     "timing sample faster than every baseline sample? Account for workload size, key cardinality, allocation, "
     "parsing and sorting costs. No result for this candidate is available yet."},
]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def call_state(call: dict) -> tuple[str, str]:
    request = call["request"]
    if "messages" in request:
        return (next(m["content"] for m in request["messages"] if m["role"] == "system"),
                next(m["content"] for m in request["messages"] if m["role"] == "user"))
    return request["instructions"], request["input"]


def budget_in(state: str) -> dict:
    return json.JSONDecoder().raw_decode(state.rsplit("## Budget", 1)[1].lstrip())[0]


def prepare_bundle(bundle: Path) -> list[dict]:
    report = json.loads((bundle / "report.json").read_text())
    if report["task"]["split"] not in {"A", "B"} or report.get("scripted_model"):
        raise ValueError("only real-model A/B development bundles are eligible")
    calls = sorted((bundle / "model_calls").glob("m*.json"), key=lambda p: int(p.stem[1:]))
    states = {p.stem: call_state(json.loads(p.read_text())) for p in calls}
    steps, cases = report["steps"], []
    source = {"run_id": report["run_id"], "task_id": report["task"]["task_id"], "split": report["task"]["split"],
              "report_sha256": hashlib.sha256((bundle / "report.json").read_bytes()).hexdigest()}
    small_requests = 0
    for call_id, (system, state) in states.items():
        budget = budget_in(state)
        if budget["current_model_role"] != "small":
            continue
        before = next(s["seq"] for s in steps if (s.get("model_call_id") or "").endswith("/" + call_id))
        model_candidates = {s["candidate_id"] for s in steps if s["seq"] < before and s["action"] == "propose_candidate"}
        misses, evaluated = 0, set()
        for step in steps:
            if step["seq"] >= before:
                break
            if (step["action"] == "run_validation" and step["candidate_id"] in model_candidates
                    and step["candidate_id"] not in evaluated):
                evaluated.add(step["candidate_id"])
                res = step["result"]
                target = res.get("run_target_speedup", report["task"]["target_min_speedup"])
                hit = res.get("status") == "passed" and res.get("improved") and (res.get("speedup") or 0) >= target
                misses = 0 if hit else misses + 1
        cases.append({"id": f"{report['run_id']}-{call_id}-route", "kind": "route", "source": {**source, "call_id": call_id},
                      "evidence": {"agent_instructions": system, "state_before_request": state}, "questions": [ROUTE_QUESTION],
                      "reference": {"historical_role": "small", "current_rule_v2": "large" if small_requests >= 3 or misses >= 2 else "small",
                                    "small_requests_used": small_requests, "consecutive_misses": misses}})
        small_requests += 1
    for proposal in steps:
        if proposal["action"] not in {"propose_candidate", "reuse_candidate"}:
            continue
        cid = proposal["candidate_id"]
        check = next((s for s in steps if s["seq"] > proposal["seq"] and s["action"] == "run_validation"
                      and s["candidate_id"] == cid), None)
        if check is None:
            continue
        if proposal["action"] == "propose_candidate":
            call_id = proposal["model_call_id"].rsplit("/", 1)[1]
            system, state = states[call_id]
            target = budget_in(state)["target_speedup"]
            evidence = {"agent_instructions": system, "state_before_request": state}
        else:
            # The first model call is after reuse. Take only its task/profile prefix, never candidate results.
            system, state = next(iter(states.values()))
            if "## Candidates" not in state:
                raise ValueError("cannot isolate task/profile before reuse results")
            target = report["task"]["target_min_speedup"]
            evidence = {"agent_instructions": system, "task_and_profile": state.split("## Candidates", 1)[0],
                        "initial_program": (bundle / "candidates" / "c0.py").read_text(),
                        "past_experience": proposal["params"], "prior_hypothesis_unverified": proposal["hypothesis"]}
        evidence.update(proposed_candidate=(bundle / "candidates" / f"{cid}.py").read_text(), target_speedup=target)
        result = check["result"]
        cases.append({"id": f"{report['run_id']}-{cid}-candidate", "kind": "candidate",
                      "source": {**source, "candidate_id": cid, "origin": proposal["action"], "step": proposal["seq"]},
                      "evidence": evidence, "questions": CANDIDATE_QUESTIONS,
                      "reference": {"correct": bool(result.get("correct")), "on_target": bool(result.get("status") == "passed"
                                    and result.get("improved") and (result.get("speedup") or 0) >= target),
                                    "dev_speedup": result.get("speedup"), "target_speedup": target,
                                    "evaluation_id": check["evaluation_id"]}})
    return cases


def compact_candidates(cases: list[dict]) -> list[dict]:
    """Diagnostic ablation: same candidate questions/labels, task profile + c0 + proposed code only."""
    compact = []
    for case in cases:
        if case["kind"] != "candidate":
            continue
        evidence = case["evidence"]
        if "state_before_request" in evidence:
            state = evidence["state_before_request"]
            initial = re.search(r"### c0\n.*?```python\n(.*?)\n```", state, flags=re.S)
            if initial is None or "## Candidates" not in state:
                raise ValueError("cannot isolate the original program and task/profile")
            task, code = state.split("## Candidates", 1)[0], initial.group(1)
        else:
            task, code = evidence["task_and_profile"], evidence["initial_program"]
        compact.append({**case, "id": case["id"] + "-compact", "evidence": {
            "task_and_profile": task, "initial_program": code,
            "proposed_candidate": evidence["proposed_candidate"], "target_speedup": evidence["target_speedup"]}})
    return compact


def summarize(records: list[dict]) -> dict:
    successful = [r for r in records if r["result"]["ok"]]
    costs = [r["cost_usd"] for r in records]
    candidates = [r for r in successful if r["case"]["kind"] == "candidate"]
    metrics = {}
    for name in ("correct", "on_target"):
        pairs = [(next(a["probability"] for a in r["answers"] if a["name"] == name), r["case"]["reference"][name]) for r in candidates]
        positive = [p for p, y in pairs if y]
        negative = [p for p, y in pairs if not y]
        metrics[name] = {
            "n": len(pairs), "actual_positive": sum(y for _, y in pairs),
            "predicted_positive": sum(p >= THRESHOLD for p, _ in pairs),
            "true_positive": sum(p >= THRESHOLD and y for p, y in pairs),
            "false_positive": sum(p >= THRESHOLD and not y for p, y in pairs),
            "false_negative": sum(p < THRESHOLD and y for p, y in pairs),
            "true_negative": sum(p < THRESHOLD and not y for p, y in pairs),
            "brier": statistics.mean((p - y) ** 2 for p, y in pairs) if pairs else None,
            "auc": (sum((p > n) + 0.5 * (p == n) for p in positive for n in negative)
                    / (len(positive) * len(negative))) if positive and negative else None,
        }
    routes = [r for r in successful if r["case"]["kind"] == "route"]
    return {"protocol": PROTOCOL, "model": MODEL, "threshold": THRESHOLD, "requests": len(records), "successes": len(successful),
            "errors": len(records) - len(successful), "input_tokens_reported": sum(r["result"]["usage"]["input_tokens"] or 0 for r in records),
            "usage_unknown_requests": sum(r["result"]["usage"]["input_tokens"] is None for r in records),
            "cost_known_usd": sum(c for c in costs if c is not None), "cost_unknown_requests": sum(c is None for c in costs),
            "price_version": PRICE_VERSION, "latency_median_s": statistics.median(r["result"]["latency_s"] for r in successful) if successful else None,
            "latency_total_s": sum(r["result"]["latency_s"] for r in records), "candidate_metrics": metrics,
            "route_count": len(routes), "route_upgrades": sum(r["answers"][0]["choice"] == "large" for r in routes),
            "route_disagreements_with_v2": sum(r["answers"][0]["choice"] != r["case"]["reference"]["current_rule_v2"] for r in routes),
            "scope": "Retrospective development replay. Route choices have no counterfactual correctness labels; "
                     "candidate gating uses historical dev outcomes, not a live rollout or final-test estimate."}


def run(cases: list[dict], out: Path, env_file: Path | None, timeout_s: float) -> dict:
    if out.exists():
        raise ValueError("use a new output directory to preserve previous attempts and billing records")
    out.mkdir(parents=True)
    if env_file:
        load_dotenv(env_file)
    records = []
    for index, case in enumerate(cases, 1):
        # Labels and source reports are never passed to the model.
        result = decide(case["evidence"], case["questions"], timeout_s=timeout_s)
        record = {"case": {k: v for k, v in case.items() if k not in {"evidence", "questions"}},
                  "timestamp": datetime.now(timezone.utc).isoformat(), "result": asdict(result),
                  "answers": json.loads(result.text) if result.ok else [], "cost_usd": estimate_decision_cost(result)}
        write_json(out / f"{index:02d}-{case['id']}.json", record)
        records.append(record)
        write_json(out / "summary.json", summarize(records))
        print(json.dumps({"case": case["id"], "ok": result.ok, "latency_s": round(result.latency_s, 3),
                          "answers": record["answers"], "error": result.error_message}, ensure_ascii=False), flush=True)
        if not result.ok:
            raise RuntimeError(f"stopped after {case['id']}: {result.error_kind}; see preserved output")
    return summarize(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare")
    build.add_argument("--bundle", type=Path, action="append", required=True)
    build.add_argument("--out", type=Path, required=True)
    compact = sub.add_parser("compact")
    compact.add_argument("--cases", type=Path, required=True)
    compact.add_argument("--out", type=Path, required=True)
    summary = sub.add_parser("summarize")
    summary.add_argument("--results", type=Path, required=True)
    replay = sub.add_parser("run")
    replay.add_argument("--cases", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)
    replay.add_argument("--env-file", type=Path)
    replay.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.command == "prepare":
        cases = [case for bundle in args.bundle for case in prepare_bundle(bundle)]
        if len({c["id"] for c in cases}) != len(cases):
            raise ValueError("duplicate replay cases")
        write_json(args.out, {"protocol": PROTOCOL, "threshold": THRESHOLD, "cases": cases})
        print(json.dumps({"cases": len(cases), "routes": sum(c["kind"] == "route" for c in cases),
                          "candidates": sum(c["kind"] == "candidate" for c in cases)}))
    elif args.command == "compact":
        fixture = json.loads(args.cases.read_text())
        write_json(args.out, {**fixture, "view": "compact", "cases": compact_candidates(fixture["cases"])})
    elif args.command == "summarize":
        records = [json.loads(p.read_text()) for p in sorted(args.results.glob("[0-9]*.json"))]
        print(json.dumps(summarize(records), ensure_ascii=False, indent=2))
    else:
        fixture = json.loads(args.cases.read_text())
        if fixture["protocol"] != PROTOCOL or fixture["threshold"] != THRESHOLD:
            raise ValueError("replay protocol mismatch")
        print(json.dumps(run(fixture["cases"], args.out, args.env_file, args.timeout), indent=2))


if __name__ == "__main__":
    main()
