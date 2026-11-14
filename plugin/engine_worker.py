"""DSH transport adapter around the real QuotaCrux Runner; JSONL over stdio.

No provider credentials enter this process. Model requests are executed by the
owning DSH plugin; candidate execution and verification stay in the core sandbox.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from quotacrux import config, db, report, taskpkg
from quotacrux.agent import actions, routing
from quotacrux.agent.runner import RunOptions, Runner
from quotacrux.llm.base import LLMResult, Usage


def emit(kind: str, **data) -> None:
    print(json.dumps({"kind": kind, **data}, ensure_ascii=False, default=str), flush=True)


TASKS = {
    "groupagg": {"rows": 300_000, "keys": 5000, "order": "random", "skew": 0.8},
    "logstats": {"rows": 100_000, "endpoints": 150, "hours": 24, "error_rate": 0.04, "order": "time"},
    "intervals": {"rows": 200_000, "value_max": 8_000_000, "length_mean": 40},
}


class BridgeClient:
    def __init__(self, model_config, runner):
        self.config, self.runner = model_config, runner

    def complete(self, system, user, schema, timeout_s, max_output_tokens):
        call_id = f"m{self.runner.requests_used + 1}"
        body = {"system": system, "user": user, "schema": schema, "max_output_tokens": max_output_tokens}
        emit("model_request", call_id=call_id, role=self.config.role, model=self.config.model,
             timeout_s=timeout_s, **body)
        started = time.perf_counter()
        line = sys.stdin.readline()
        if not line:
            db.update("runs", "run_id", self.runner.run_id, {"stop_requested": 1})
            return LLMResult(False, None, Usage(), time.perf_counter() - started, error_kind="network",
                             error_message="DSH bridge closed", request_body=body)
        response = json.loads(line)
        if response.get("call_id") != call_id:
            raise RuntimeError("DSH bridge response does not match the pending model call")
        if response.get("canceled"):
            db.update("runs", "run_id", self.runner.run_id, {"stop_requested": 1})
        usage = response.get("usage") or {}
        return LLMResult(
            bool(response.get("ok")), response.get("text"),
            Usage(input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
                  cached_input_tokens=usage.get("cached_input_tokens"), reasoning_tokens=usage.get("reasoning_tokens"),
                  source="reported" if usage.get("input_tokens") is not None else "unknown", raw=usage),
            time.perf_counter() - started, model_returned=response.get("model_returned"),
            error_kind=response.get("error_kind"), error_message=response.get("error_message"),
            request_body=response.get("request_body") or body, response_body=response,
        )


class DemoRunner(Runner):
    """Local-first demo policy; base Runner/validators/memory remain authoritative."""

    def __init__(self, request):
        self.request = request
        self.remote_used = 0
        self.remote_limit = request["remote_limit"]
        self.last_remote_reason = None
        self.remote_block_logged = False
        self.stop_file = Path(request["stop_file"])
        super().__init__(RunOptions(
            task_id=f"dsh-demo-{request['family']}-v1", mode="online", router=False,
            label=f"DSH {request['session_id']}",
            limits=config.RunLimits(max_model_requests=6, max_candidates=4, wall_clock_s=240,
                                    model_request_timeout_s=90, token_budget=100_000),
        ))
        self.model_cfgs = {
            "small": config.ModelConfig(provider="chat_compat", model=request["small_model"], role="small",
                                        base_url=request["small_base_url"], max_output_tokens=4096,
                                        reasoning_effort="none", enable_thinking=False),
            "large": config.ModelConfig(provider="dsh_usa0", model=request["large_model"], role="large",
                                        base_url=f"dsh://{request['large_provider']}", max_output_tokens=4096),
        }
        self.clients = {role: BridgeClient(value, self) for role, value in self.model_cfgs.items()}
        self.action_router, self.model_router = routing.make_routers(self.opts.routing, self.clients, self.model_cfgs)
        self.system_prompt += (
            "\nUser research request (the correctness contract and evaluator remain fixed):\n"
            + request["text"][:4096]
            + "\nPrefer a concrete candidate over long analysis. Remote assistance is limited; all correctness claims require validation."
        )
        self.system_prompt_sha = hashlib.sha256(self.system_prompt.encode()).hexdigest()

    def _config(self):
        value = super()._config()
        value["demo_policy"] = {"version": "local-first-bounded-assistance-v1", "remote_limit": self.remote_limit,
                                "expert_review_requested": self.request["expert_review"],
                                "session_id": self.request["session_id"],
                                "input_sha256": hashlib.sha256(self.request["text"].encode()).hexdigest()}
        value["fingerprint"] = hashlib.sha256(db.dumps({"core": value["fingerprint"],
            "policy": {k: v for k, v in value["demo_policy"].items() if k != "session_id"}}).encode()).hexdigest()[:16]
        return value

    def _route(self):
        self.role = "small"
        self.route = {"router": "demo-local-first-v1", "route": "small", "reason": "local_first",
                      "model": self.model_cfgs["small"].model, "family": self.task.family,
                      "remote_limit": self.remote_limit}
        self._step("program", "route_model", "done", purpose="先复验项目经验；未能直接交付时优先本机模型，远程只按需限额求助",
                   result=self.route, next_decision="local model first")
        db.add_event(self.run_id, "model_routed", self.route)

    def _select_model(self):
        if self.role == "large" and self.remote_used >= self.remote_limit:
            self.role = "small"
            db.add_event(self.run_id, "returned_to_local", {"reason": "远程本次工作已完成，后续交还本机模型与程序", "remote_used": self.remote_used})
        if self.remote_used >= self.remote_limit:
            return True
        return super()._select_model()

    def _upgrade(self, reason):
        if self.remote_used >= self.remote_limit:
            self.role = "small"
            if not self.remote_block_logged:
                db.add_event(self.run_id, "remote_limit_reached", {"limit": self.remote_limit, "reason": "远程额度已用完，继续本地执行"})
                self.remote_block_logged = True
            return
        self.last_remote_reason = reason
        db.add_event(self.run_id, "remote_requested", {"reason": reason, "trigger": "validation_feedback", "limit": self.remote_limit})
        super()._upgrade(reason)

    def _invoke(self, cfg, request):
        if cfg.role == "large":
            if self.remote_used >= self.remote_limit:
                raise RuntimeError("remote call quota would be exceeded")
            self.remote_used += 1
        result = super()._invoke(cfg, request)
        if not result[0].ok:
            emit("model_failure", call_id=result[1], role=cfg.role, error=result[0].error_message)
        if self.stop_file.exists():
            db.update("runs", "run_id", self.run_id, {"stop_requested": 1})
        return result

    def _before_request(self, required_requests=1):
        if self.stop_file.exists():
            db.update("runs", "run_id", self.run_id, {"stop_requested": 1})
        return super()._before_request(required_requests)

    def _step(self, actor, action, status, **kwargs):
        result = super()._step(actor, action, status, **kwargs)
        call_id = kwargs.get("model_call_id")
        if call_id:
            row = db.one("SELECT role, model_requested FROM model_calls WHERE call_id=?", (f"{self.run_id}/{call_id}",))
            if row:
                emit("work_recorded", call_id=call_id, role=row["role"], model=row["model_requested"], action=action,
                     status=status, purpose=kwargs.get("purpose"), candidate_id=kwargs.get("candidate_id"),
                     analysis=(kwargs.get("params") or {}).get("analysis"),
                     evidence=kwargs.get("result") or {}, reason=self.last_remote_reason if row["role"] == "large" else None)
        return result

    def _final_evaluation(self):
        if self.stop_file.exists():
            self._stop("user_stopped", "DSH stop requested; current step completed")
        if (self.request["expert_review"] and self.best_id and self.remote_used < self.remote_limit
                and not self._budget_block() and self.stop_reason not in {"user_stopped", "model_api_error", "internal_error", "environment_error"}):
            self.last_remote_reason = "用户明确请求一次专家复核：只审阅开发结果与候选程序，不接触隐藏最终测试"
            db.add_event(self.run_id, "remote_requested", {"reason": self.last_remote_reason, "trigger": "user_requested_review", "limit": self.remote_limit})
            cfg = self.model_cfgs["large"]
            schema = {**actions.ACTION_SCHEMA, "properties": {**actions.ACTION_SCHEMA["properties"], "action": {"type": "string", "enum": ["analyze"]}}}
            state = self._state() + "\nReview the best dev-validated program for correctness risks and optimizations. Return action=analyze only, put the review in analysis. This is not a final validation. Do not return code."
            started = db.now()
            res, call_id, _ = self._invoke(cfg, lambda timeout: self.clients["large"].complete(self.system_prompt, state, schema, timeout, 2048))
            if res.ok:
                try:
                    act = actions.parse(res.text or "")
                    if act.action != "analyze":
                        raise actions.InvalidAction("review_action", "expert review must return analyze")
                    self._do_analyze(act, call_id, started)
                except actions.InvalidAction as exc:
                    self._invalid(started, call_id, exc, raw=res.text)
            else:
                self._step("model", "expert_review", "error", model_call_id=call_id,
                           purpose="专家复核未完成；保留真实错误，不将其视为验证通过", result={"error": res.error_message})
            self.role = "small"
        super()._final_evaluation()


def project_stats():
    rows = db.all_rows("SELECT role, COUNT(*) AS n FROM model_calls GROUP BY role")
    counts = {row["role"]: row["n"] for row in rows}
    return {"local": counts.get("small", 0), "remote": counts.get("large", 0),
            "runs": db.one("SELECT COUNT(*) AS n FROM runs")["n"],
            "reused_runs": db.one("SELECT COUNT(DISTINCT run_id) AS n FROM candidates WHERE origin='experience'")["n"]}


def main():
    request = json.loads(sys.stdin.readline())
    family = request.get("family")
    if family not in TASKS or request.get("remote_limit") not in (0, 1):
        raise ValueError("unsupported demonstration task or remote quota")
    db.get()
    emit("project_history", stats=project_stats())
    task_id = f"dsh-demo-{family}-v1"
    if not db.one("SELECT task_id FROM tasks WHERE task_id=?", (task_id,)):
        taskpkg.build_task(family, {"task_id": task_id, "family": family, "split": "smoke", "params": TASKS[family],
                                   "dev_seed": 151101, "final_seed": 151102, "examples_seed": 151103,
                                   "notes": "DSH live demo v1; independent dev/final; real candidate validation"})
    runner = DemoRunner(request)
    with db.observe_events(lambda event: emit("engine_event", event=event)):
        runner.create()
        result = runner.execute()
    # The full reproducible report remains under the project-scoped engine store.
    emit("result", report=result, project_stats=project_stats(), report_path=str(runner.dir / "report.json"),
         best_path=(result.get("best_candidate") or {}).get("code_path"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit("fatal", error=f"{type(exc).__name__}: {exc}")
        sys.exit(1)
