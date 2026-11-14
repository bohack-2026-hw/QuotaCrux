"""Fixed evaluator: correctness against hidden reference output, then alternating baseline/candidate timing.

The evaluator owns the reference data and the clock; candidates only ever see their stdin.
"""

from __future__ import annotations

import statistics
import time
import uuid
from dataclasses import dataclass, field

from . import config, db
from .sandbox import executor
from .taskpkg import Task, sha256_bytes

EVALUATOR_VERSION = "runtime-suite-eval-3"

# Sample statuses that mean the candidate itself misbehaved, as opposed to the sandbox failing.
CANDIDATE_FAILURES = {"compile_error", "runtime_error", "timeout", "output_limit", "memory_limit"}


@dataclass
class Evaluation:
    evaluation_id: str
    task_id: str
    dataset: str
    # passed | wrong_output | format_error | contract_violation | <sample failure> | unstable | sandbox_error | baseline_failed | checker_error
    status: str
    executed: bool  # the program ran to completion on the first sample
    format_ok: bool | None
    correct: bool | None
    improved: bool | None
    goal_met: bool | None
    speedup: float | None
    candidate_median_s: float | None
    baseline_median_s: float | None
    detail: dict = field(default_factory=dict)
    started_at: str = ""
    ended_at: str = ""

    def public_feedback(self) -> dict:
        """What the agent may see about a dev evaluation."""
        fb = {
            "evaluation_id": self.evaluation_id,
            "status": self.status,
            "executed": self.executed,
            "format_ok": self.format_ok,
            "correct": self.correct,
            "speedup": self.speedup,
            "improved": self.improved,
            "goal_met": self.goal_met,
            "candidate_median_s": self.candidate_median_s,
            "baseline_median_s": self.baseline_median_s,
        }
        if self.detail.get("failure"):
            fb["failure"] = self.detail["failure"]
        if self.detail.get("timing"):
            t = self.detail["timing"]
            fb["timing_spread"] = {"candidate_min_max_s": t["candidate_min_max_s"], "baseline_min_max_s": t["baseline_min_max_s"]}
        return fb


def _spread(xs: list[float]) -> dict:
    qs = statistics.quantiles(xs, n=4) if len(xs) >= 2 else [xs[0]] * 3
    return {"median": statistics.median(xs), "min": min(xs), "max": max(xs), "iqr": qs[2] - qs[0]}


def evaluate(
    task: Task,
    code: bytes,
    dataset: str,
    measure: config.MeasureConfig,
    limits: config.RunLimits,
    *,
    run_id: str | None = None,
    candidate_id: str | None = None,
    measure_timing: bool = True,
    baseline_code: bytes | None = None,
) -> Evaluation:
    started = db.now()
    t_start = time.perf_counter()
    cases = task.adapter.cases(task, dataset)
    baseline_code = baseline_code if baseline_code is not None else task.initial_code.encode()
    timeout = limits.measurement_timeout_s
    samples: list[dict] = []
    ev = Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "pending", False, None, None, None, None, None, None, None)

    def record(who: str, kind: str, r: executor.SampleResult) -> None:
        samples.append({"who": who, "kind": kind, **r.summary()})

    def fail(status: str, failure: dict | None = None) -> Evaluation:
        ev.status = status
        if failure:
            ev.detail["failure"] = failure
        return ev

    def sample_failure(r: executor.SampleResult) -> dict:
        tail = r.stderr_tail.strip().splitlines()[-12:]
        return {"category": r.status, "exit_code": r.exit_code, "stderr_tail": "\n".join(tail)}

    def suite(src: bytes, who: str, kind: str, selected) -> tuple[float | None, dict | None]:
        outputs, elapsed, output_bytes = [], 0.0, 0
        for case in selected:
            r = executor.run_sample(src, case.input, timeout, measure)
            record(who, f"{kind}:{case.name}", r)
            if r.status != "ok":
                return None, {**sample_failure(r), "case": case.name}
            output_bytes += len(r.stdout)
            if output_bytes > measure.max_output_bytes:
                return None, {"category": "output_limit", "case": case.name, "message": "suite stdout exceeded output budget"}
            outputs.append(r.stdout)
            elapsed += r.elapsed_s
        check = task.adapter.check_outputs(task, selected, outputs, measure, limits)
        if who == "candidate":
            ev.executed = True
            ev.format_ok, ev.correct = check["format_ok"], check["correct"]
        return elapsed, check.get("failure")

    def failed(who: str, failure: dict, *, timed: bool = False) -> Evaluation:
        category = failure["category"]
        if category in ("sandbox_error", "checker_error"):
            return fail(category, failure)
        if who == "baseline":
            return fail("baseline_failed", failure)
        if timed:
            return fail("unstable", failure)
        return fail(category, failure)

    try:
        # The adapter owns case data and judging; the loop owns execution order and timing.
        _, failure = suite(code, "candidate", "warmup_check", cases)
        if failure:
            return failed("candidate", failure)

        for case in task.adapter.public_cases(task):
            _, failure = suite(code, "candidate", "contract", [case])
            if failure:
                if failure["category"] in ("wrong_output", "format_error"):
                    return fail("contract_violation", {"category": "contract_violation", "contract_case": case.name,
                                                       "input": case.input.decode(), "expected": case.expected.decode(), "check": failure})
                return failed("candidate", {**failure, "contract_case": case.name})
        if not measure_timing:
            ev.status = "passed"
            return ev

        _, failure = suite(baseline_code, "baseline", "warmup_check", cases)
        if failure:
            return failed("baseline", failure)
        cand_t, base_t = [], []
        for i in range(measure.repeats):
            order = ("baseline", "candidate") if i % 2 == 0 else ("candidate", "baseline")
            for who in order:
                src = baseline_code if who == "baseline" else code
                elapsed, failure = suite(src, who, f"measure_{i}", cases)
                if failure:
                    return failed(who, failure, timed=True)
                (base_t if who == "baseline" else cand_t).append(elapsed)

        cs, bs = _spread(cand_t), _spread(base_t)
        ev.candidate_median_s, ev.baseline_median_s = cs["median"], bs["median"]
        ev.speedup = round(bs["median"] / cs["median"], 4)
        # Improvement must not be explainable by noise: every candidate sample beats every baseline sample
        # (one-sided Mann-Whitney U = 0; p = 1/252 for 5 vs 5). The goal additionally needs the target speedup.
        ev.improved = cs["max"] < bs["min"]
        ev.goal_met = ev.improved and ev.speedup >= task.target_min_speedup
        ev.detail["timing"] = {
            "candidate_s": cand_t, "baseline_s": base_t, "candidate": cs, "baseline": bs,
            "candidate_min_max_s": [cs["min"], cs["max"]], "baseline_min_max_s": [bs["min"], bs["max"]],
            "method": f"1 warm-up suite each, {measure.repeats} alternating rounds; each sample sums case runtimes; median ratio",
            "cases_per_sample": len(cases),
            "improved_rule": "all candidate samples faster than all baseline samples",
        }
        ev.status = "passed"
        return ev
    finally:
        ev.started_at, ev.ended_at = started, db.now()
        ev.detail["samples"] = samples
        ev.detail["duration_s"] = round(time.perf_counter() - t_start, 3)
        ev.detail["container_ready_latency_s"] = round(sum(s["ready_latency_s"] or 0 for s in samples), 3)
        ev.detail["dataset_sha256"] = task.manifest["files"][f"{dataset}_input"]["sha256"]
        db.insert("evaluations", {
            "evaluation_id": ev.evaluation_id, "run_id": run_id, "candidate_id": candidate_id,
            "task_id": task.task_id, "dataset": dataset, "dataset_sha256": ev.detail["dataset_sha256"],
            "status": ev.status, "executed": int(ev.executed),
            "format_ok": _b(ev.format_ok), "correct": _b(ev.correct), "improved": _b(ev.improved), "goal_met": _b(ev.goal_met),
            "speedup": ev.speedup, "candidate_median_s": ev.candidate_median_s, "baseline_median_s": ev.baseline_median_s,
            "detail_json": db.dumps({**ev.detail, "candidate_sha256": sha256_bytes(code)}),
            "evaluator_version": EVALUATOR_VERSION, "started_at": ev.started_at, "ended_at": ev.ended_at,
        })


def _b(v: bool | None) -> int | None:
    return None if v is None else int(v)


def profile_candidate(task: Task, code: bytes, measure: config.MeasureConfig, limits: config.RunLimits) -> dict:
    """Evidence tool: cProfile of the candidate on dev input. Output correctness is reported, not the data."""
    cases = task.adapter.cases(task, "dev")
    case = cases[0]
    r = executor.run_sample(code, case.input, limits.measurement_timeout_s * 3, measure, profile=True)
    text = r.stderr_tail
    begin, end = text.find("ROUTEEVO_PROFILE_BEGIN"), text.find("ROUTEEVO_PROFILE_END")
    report = text[begin + len("ROUTEEVO_PROFILE_BEGIN"): end].strip() if 0 <= begin < end else None
    check = task.adapter.check_outputs(task, [case], [r.stdout], measure, limits) if r.status == "ok" else {}
    return {
        "status": (check.get("failure") or {}).get("category", r.status),
        "case": case.name, "dev_cases": len(cases),
        "profiled_elapsed_s": r.elapsed_s,
        "note": "cProfile of the first dev case adds overhead; use relative cumulative times, not absolute speed",
        "output_correct": check.get("correct"),
        "profile": report,
        "stderr_tail": None if report else "\n".join(text.strip().splitlines()[-12:]),
    }
