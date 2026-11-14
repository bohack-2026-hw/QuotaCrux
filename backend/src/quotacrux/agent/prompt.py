"""System prompt (fixed, versioned) and the per-request state message."""

from __future__ import annotations

import hashlib
import json

PROMPT_VERSION = "agent-prompt-v7"

SYSTEM_PROMPT = """\
You are the decision module of QuotaCrux, an agent that optimizes a Python program under a hard correctness constraint.
Each request you receive describes the full current state. Reply with exactly one JSON object choosing the next action.

Goal and rules
- The program must stay correct for every input that satisfies the contract. An external evaluator checks the output
  against hidden reference data; you never see the evaluator, the reference output or the hidden final test data.
  Task-specific correctness checks and any public contract cases are described in the task state.
- Primary metric: speedup = median runtime of the initial program / median runtime of the candidate, measured on the
  task's dev data in a Docker container (1 CPU, 1 GB memory, no network, read-only filesystem, a fresh process per
  case, input on stdin). A timing sample sums the runtimes of all cases in the selected suite.
  A candidate counts as improved only if every timed candidate sample is faster than every
  baseline sample; the goal is an improved candidate with speedup >= the target. When a candidate reaches it, the run
  stops and that candidate is frozen and tested once on hidden final data of the same task.
- Candidates are complete single-file programs using only the Python 3.12 standard library. They read stdin and write
  stdout. Nothing persists between samples, so caching across runs is impossible.
- Budgets are enforced by the program. Every reply consumes one model request. Candidates are limited.

Actions (set every field; fields an action does not use must be null)
- analyze: reason about the evidence so far. Put the reasoning in `analysis`. No program effect.
- get_evidence: run a tool. `tool` = "profile_candidate" runs cProfile on `candidate_id` with the dev input and returns
  the top functions by cumulative time and whether the output was correct.
- propose_candidate: submit a full program in `code`, with `parent_candidate_id` naming the candidate it modifies.
  The program checks and validates it immediately; you see the result in the next request.
- run_validation: re-measure an existing `candidate_id` on dev data (e.g. when timing looks noisy).
- finish: stop the run when further attempts are unlikely to help. Explain in `finish_reason`.

Always fill `purpose` (why this action now), `expected_result` (what you expect to observe) and `verification`
(how the result will be checked). Put an unverified causal explanation in `hypothesis`; it is stored as a hypothesis,
not a fact. Write purpose, expected_result, verification, hypothesis, analysis and finish_reason in Simplified Chinese.

Experience records, when provided, come from earlier runs: the observed workload conditions, the change that was tried
and the measured result, including failures. They are evidence, not rules. Check that their conditions match the
current workload before relying on them, and mind their sample counts.

Before your first request the program re-validates up to three verified programs from the experience snapshot whose
conditions are closest to this workload; they appear as candidates with origin "experience" and their results are real
measurements on this task. To keep requests short, only the code of the best of them is shown; the others are listed
with their results. You are only asked when none of them reached the target, or in a learning run, where the target in
Budget (`target_speedup`) is raised above the best of them: then a candidate must beat that program, so build on it
(set it as parent) rather than on c0, and do not resubmit a program that is already in the list.
"""

SYSTEM_PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()


def system_prompt(task, research_mode: str) -> str:
    if research_mode == "legacy" and not task.is_native:
        return SYSTEM_PROMPT
    controls = {
        "independent": "Each request is an independent attempt from c0. Propose a complete fresh candidate with parent c0, "
                       "or finish. Other attempts' code and feedback are hidden; an external selector keeps the best feasible result.",
        "no_feedback": "Retain and refine your own code, analysis and hypotheses within this run. The frozen initial c0 "
                       "evaluation is public. All subsequent evaluation results, including c0 rechecks, scores, timing, "
                       "errors, rankings and the actual best candidate are withheld. All submitted candidates remain visible "
                       "regardless of validity. An external selector still chooses the best feasible candidate. Choose an explicit "
                       "parent; an omitted parent defaults to c0. Protocol-format errors remain visible. Request/candidate counts "
                       "and total elapsed budget time remain visible; elapsed time includes model and evaluation work.",
        "feedback": "Use this run's actual feedback to refine hypotheses and candidates.",
    }
    control = controls.get(research_mode, controls["feedback"]) + (
        " Continue improving within the budget; meeting an intermediate threshold does not stop the research. "
        "Finish when further experiments are unlikely to help.")
    menu = ["Actions (set every field; unused fields must be null):",
            "- propose_candidate: submit a complete program in code and its parent_candidate_id (defaults to c0). It is evaluated immediately.",
            "- finish: end research; explain the decision in finish_reason. The external selector freezes the deliverable."]
    if research_mode != "independent":
        menu += ["- analyze: put your reasoning in analysis and an unverified explanation in hypothesis; no program effect.",
                 "- run_validation: re-evaluate an existing candidate_id on dev data."]
        if not task.is_native:
            menu.append('- get_evidence: tool="profile_candidate" profiles candidate_id on dev data.')
    menu.append("Every action, including analyze and finish, requires non-empty purpose, expected_result and verification. "
                "Write purpose, expected_result, verification, hypothesis, analysis and finish_reason in Simplified Chinese. "
                "Hypotheses are your conjectures, not externally verified facts.")
    scoring = ("Among candidates passing every feasibility check, the highest raw total score wins; improve on c0's score."
               if task.objective["metric"] == "score" else
               "Speedup is baseline median time divided by candidate median time. A correct candidate counts as improved "
               "and can replace c0 only when EVERY measured candidate sample is faster than EVERY baseline sample "
               "(max(candidate times) < min(baseline times)). A median speedup above 1 or the target alone is insufficient. "
               "The external selector applies these ranges. The target is a milestone, not a stopping condition.")
    example = {"action": "propose_candidate", "purpose": "说明本次改动目的", "expected_result": "写明预期结果",
               "verification": "写明验证方法", "hypothesis": None, "analysis": None, "tool": None,
               "candidate_id": None, "parent_candidate_id": "c0", "code": "<complete Python code>", "finish_reason": None}
    examples = [example]
    if research_mode != "independent":
        examples.append({**example, "action": "analyze", "code": None, "parent_candidate_id": None,
                         "analysis": "说明下一步实验的推理", "hypothesis": "写出待检验的解释"})
    examples.append({**example, "action": "finish", "code": None, "parent_candidate_id": None,
                     "purpose": "结束本轮研究", "expected_result": "交付外部选择器保留的候选",
                     "verification": "对已冻结候选执行独立最终验收", "finish_reason": "说明停止理由"})
    return ("You are QuotaCrux's research execution module. Reply with exactly one JSON action.\n"
            "The task contract specifies the candidate interface, installed libraries, objective and evaluator. "
            "Preserve correctness/feasibility for every valid input. Never access private tests, evaluator code or answers. "
            "All model, compilation and tool work consumes the episode budget.\n" + control + "\n" + scoring + "\n" +
            ("This task uses a native evaluator; profiling is unavailable.\n" if task.is_native else "") + "\n".join(menu) +
            "\nJSON examples (replace the values; return ONE object):\n" +
            "\n".join(json.dumps(item, ensure_ascii=False) for item in examples))


def _block(title: str, body: str) -> str:
    return f"## {title}\n{body.rstrip()}\n"


def build_state(
    *,
    task,
    candidates: list[dict],
    hide_code: set[str] | None = None,
    evidence: list[dict],
    history: list[dict],
    experiences: list[dict] | None,
    snapshot_id: str,
    experience_summary: dict | None = None,
    budget: dict,
    last_feedback: dict | None,
) -> str:
    examples = "\n".join(
        f"Example {i + 1} input:\n```\n{ex['input']}```\nExample {i + 1} output:\n```\n{ex['output']}```"
        for i, ex in enumerate(task.examples)
    )
    parts = [
        _block("Task", f"task_id: {task.task_id}\nfamily: {task.family}\nobjective: {json.dumps(task.objective)}\n\n{task.contract}"),
        _block("Evaluation protocol", task.presentation["agent_notes"]),
        _block("Visible examples", examples),
        _block("Dev data profile (the timed input; computed by the program)", json.dumps(task.dev_profile, indent=2)),
    ]

    cand_lines = []
    for c in candidates:
        head = {k: c[k] for k in ("candidate_id", "origin", "experience_id", "parent_candidate_id", "latest_evaluation") if k in c}
        if c["candidate_id"] in (hide_code or set()):
            cand_lines.append(f"### {c['candidate_id']}\n{json.dumps(head, ensure_ascii=False, indent=2)}\n"
                              "(code omitted: a re-validated program from experience that is not the best of them)")
        else:
            cand_lines.append(f"### {c['candidate_id']}\n{json.dumps(head, ensure_ascii=False, indent=2)}\n```python\n{c['code']}\n```")
    description = ("actual best is withheld" if budget.get("best_result_visibility") == "withheld"
                   else "best so far is marked in budget")
    parts.append(_block(f"Candidates (c0 is the initial program; {description})", "\n".join(cand_lines)))

    if evidence:
        ev_lines = [f"### {e['tool']} on {e['candidate_id']} (step {e['step']})\n{json.dumps(e['result'], ensure_ascii=False, indent=2)}" for e in evidence]
        parts.append(_block("Evidence collected in this run", "\n".join(ev_lines)))

    if experiences:
        exp_lines = []
        for e in experiences:
            change = dict(e["change"])
            diff = change.pop("diff_vs_initial_program", "")
            meta = {**{k: v for k, v in e.items() if k != "change"}, "change": change}
            exp_lines.append(f"### {e['experience_id']} ({e['outcome']})\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n"
                             f"Change as a diff against the initial program:\n```diff\n{diff}\n```")
        counts = ""
        if experience_summary:
            counts = (f"Snapshot holds {experience_summary['snapshot_size']} records; "
                      f"{sum(experience_summary['matched_by_outcome'].values())} match this workload on at least "
                      f"{experience_summary['min_matches']} of {experience_summary['feature_count']} features "
                      f"(by outcome: {json.dumps(experience_summary['matched_by_outcome'])}); "
                      f"{len(experiences)} are shown.\n")
        parts.append(_block(f"Experience records from snapshot {snapshot_id}", counts + "\n".join(exp_lines)))
    else:
        parts.append(_block(f"Experience records from snapshot {snapshot_id}", "none"))

    if history:
        parts.append(_block("Steps so far", "\n".join(json.dumps(h, ensure_ascii=False) for h in history)))
    if last_feedback:
        parts.append(_block("Feedback on your previous reply", json.dumps(last_feedback, ensure_ascii=False, indent=2)))
    parts.append(_block("Budget", json.dumps(budget, ensure_ascii=False, indent=2)))
    parts.append("Reply with one JSON object for the next action.")
    return "\n".join(parts)
