"""The single execution loop: build state -> model picks an action -> program checks and executes -> evaluator feedback.

Runs are globally serial (one file lock) so model inference and other runs never overlap candidate timing.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import config, db, evaluator, memory, report, taskpkg
from ..llm.base import LLMResult
from ..llm.chat_compat import ChatCompatClient
from ..llm.openai_responses import OpenAIResponsesClient
from ..llm.pricing import NOT_BILLED_ERRORS, estimate_cost
from ..llm.scripted import ScriptedClient
from ..sandbox import executor
from . import actions, prompt

# v1 (used for A learning and the B comparison) only counted candidate misses. B showed that a small model can
# spend its requests on analysis without producing a second miss, so the switch never happened. v2 also caps the
# small model's requests without an on-target candidate. Applied to every snapshot alike.
UPGRADE_RULE = {
    "id": "upgrade-rule-v2",
    "description": "start with the small model; switch to the large model for the rest of the run, if model requests "
                   "remain, after 2 consecutive candidate attempts that are not correct-and-on-target or after 3 small-model "
                   "requests without an on-target candidate",
    "consecutive_misses": 2,
    "max_small_requests_without_goal": 3,
}
API_ERRORS = {"timeout", "network", "rate_limit", "http_5xx", "http_4xx", "config"}
FATAL_API_ERRORS = {"config", "http_4xx"}
MAX_CONSECUTIVE_API_ERRORS = 2
NO_FINAL_EVAL = {"user_stopped", "environment_error", "internal_error"}
# Records from runs that ended this way may reflect a broken environment, so they are not published.
NO_PUBLISH = {"environment_error", "internal_error"}


class RunBusy(RuntimeError):
    pass


@dataclass
class RunOptions:
    task_id: str
    mode: str = "eval"  # learn | eval
    snapshot_id: str | None = None  # default: active snapshot
    limits: config.RunLimits = field(default_factory=config.RunLimits)
    measure: config.MeasureConfig = field(default_factory=config.MeasureConfig)
    script: Path | None = None  # scripted stand-in model, functional checks only
    label: str | None = None
    research_mode: str | None = None  # legacy | feedback | independent
    fixed_model: str | None = None  # small | large; research comparisons default to small
    final_evaluation: bool = True


def _make_clients(opts: RunOptions) -> tuple[dict, dict[str, config.ModelConfig]]:
    """Real clients per role; a script replaces only the roles it lists (e.g. scripted small + real large)."""
    cfgs = config.default_model_configs()
    scripted_roles = set(json.loads(opts.script.read_text())) if opts.script else set()
    clients = {}
    for role, c in list(cfgs.items()):
        if role in scripted_roles:
            cfgs[role] = config.ModelConfig(provider="scripted", model=f"scripted-{role}", role=role,
                                            max_output_tokens=c.max_output_tokens, extra={"script": str(opts.script)})
            clients[role] = ScriptedClient(cfgs[role], opts.script)
        elif c.provider == "openai_responses":
            clients[role] = OpenAIResponsesClient(c)
        else:
            clients[role] = ChatCompatClient(c)
    return clients, cfgs


class Runner:
    def __init__(self, opts: RunOptions):
        if opts.mode not in ("learn", "eval"):
            raise ValueError("mode must be learn or eval")
        self.opts = opts
        self.task = taskpkg.load(opts.task_id)
        opts.research_mode = opts.research_mode or ("feedback" if self.task.is_native else "legacy")
        if opts.research_mode not in ("legacy", "feedback", "independent"):
            raise ValueError("invalid research mode")
        if opts.fixed_model not in (None, "small", "large"):
            raise ValueError("fixed_model must be small or large")
        if opts.research_mode != "legacy":
            if opts.mode != "eval" or opts.snapshot_id not in (None, "v0"):
                raise ValueError("research comparisons require eval mode and empty snapshot v0")
            opts.snapshot_id = "v0"
            opts.fixed_model = opts.fixed_model or "small"
        if self.task.is_native and opts.mode != "eval":
            raise ValueError("native research benchmarks currently support eval mode only")
        self.system_prompt = prompt.system_prompt(self.task, opts.research_mode)
        self.system_prompt_sha = hashlib.sha256(self.system_prompt.encode()).hexdigest()
        if opts.mode == "learn" and self.task.split not in memory.LEARNABLE_SPLITS:
            raise ValueError(f"task {self.task.task_id} is in split {self.task.split}; only {sorted(memory.LEARNABLE_SPLITS)} "
                             "tasks may write experience (B/C run in eval mode with a frozen snapshot)")
        self.limits, self.measure = opts.limits, opts.measure
        self.clients, self.model_cfgs = _make_clients(opts)
        active = db.one("SELECT value FROM settings WHERE key = 'active_snapshot_id'")["value"]
        self.snapshot_id = opts.snapshot_id or active
        if not db.one("SELECT 1 FROM snapshots WHERE snapshot_id = ?", (self.snapshot_id,)):
            raise KeyError(f"snapshot {self.snapshot_id} does not exist")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self.run_id = f"run-{stamp}-{uuid.uuid4().hex[:4]}"
        self.dir = config.RUNS_DIR / self.run_id
        self._lock_fd = None

        self.seq = 0
        self.role = opts.fixed_model or "small"
        self.requests_used = 0
        self.tokens_used = 0
        self.model_candidates = 0
        self.misses = 0
        self.small_requests = 0
        self.api_errors_in_row = 0
        self.candidates: dict[str, dict] = {}
        self.best_id: str | None = None
        self.evidence: list[dict] = []
        self.history: list[dict] = []
        self.last_feedback: dict | None = None
        self.experiences: list[dict] = []
        self.experience_summary: dict | None = None
        self.stop_reason: str | None = None
        self.stop_detail: str | None = None
        self.run_target = self.task.target_min_speedup
        self.t0 = 0.0

    # ---------- setup ----------

    def create(self) -> str:
        """Take the global run lock and persist the run with its frozen configuration."""
        config.VAR_DIR.mkdir(parents=True, exist_ok=True)
        fd = open(config.RUN_LOCK_PATH, "a+")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fd.close()
            raise RunBusy("another run is in progress; runs are serial so timings do not interfere") from None
        self._lock_fd = fd
        try:
            # Holding the lock proves no other run is alive; any 'running' row is left over from a killed process.
            db.get().execute("UPDATE runs SET status = 'interrupted', stop_reason = COALESCE(stop_reason, 'process_interrupted'),"
                             " ended_at = COALESCE(ended_at, ?) WHERE status = 'running'", (db.now(),))
            self.env = (self.task.adapter.environment_info(self.task, self.measure) if self.task.is_native
                        else executor.environment_info(self.measure))
            cfg = self._config()
            for sub in ("candidates", "calls", "tools"):
                (self.dir / sub).mkdir(parents=True, exist_ok=True)
            db.insert("runs", {
                "run_id": self.run_id, "task_id": self.task.task_id, "mode": self.opts.mode, "snapshot_id": self.snapshot_id,
                "config_json": db.dumps(cfg), "config_fingerprint": cfg["fingerprint"], "status": "running",
                "started_at": db.now(),
            })
            db.add_event(self.run_id, "run_created", {"task_id": self.task.task_id, "mode": self.opts.mode,
                                                      "snapshot_id": self.snapshot_id, "fingerprint": cfg["fingerprint"]})
        except BaseException:
            self._release()
            raise
        return self.run_id

    def _config(self) -> dict:
        comparable = {
            "task_manifest_sha256": db.one("SELECT manifest_sha256 FROM tasks WHERE task_id = ?", (self.task.task_id,))["manifest_sha256"],
            "models": {r: c.public_dict() for r, c in self.model_cfgs.items()},
            "upgrade_rule": UPGRADE_RULE,
            "prompt": {"version": prompt.PROMPT_VERSION, "system_sha256": self.system_prompt_sha},
            "research_protocol": {"mode": self.opts.research_mode, "fixed_model": self.opts.fixed_model,
                                  "final_evaluation": self.opts.final_evaluation},
            "action_schema_sha256": hashlib.sha256(json.dumps(actions.ACTION_SCHEMA, sort_keys=True).encode()).hexdigest(),
            "limits": self.limits.to_dict(),
            "measure": self.measure.to_dict(),
            "evaluator_version": evaluator.EVALUATOR_VERSION,
            "sandbox_image_id": self.env["image_id"],
            "retrieval": memory.RETRIEVAL,
            "reuse": memory.REUSE,
            "experience_extractor": memory.EXTRACTOR_VERSION,
        }
        fingerprint = hashlib.sha256(json.dumps(comparable, sort_keys=True).encode()).hexdigest()[:16]
        return {**comparable, "fingerprint": fingerprint, "environment": self.env, "label": self.opts.label,
                "scripted": sorted(r for r, c in self.model_cfgs.items() if c.provider == "scripted"),
                "fingerprint_excludes": ["mode", "snapshot_id", "label", "environment details beyond image id"]}

    def _release(self) -> None:
        if self._lock_fd:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            self._lock_fd.close()
            self._lock_fd = None

    # ---------- main ----------

    def execute(self) -> dict:
        try:
            return self._execute()
        finally:
            self._release()

    def _execute(self) -> dict:
        self.t0 = time.perf_counter()
        db.update("runs", "run_id", self.run_id, {"started_at": db.now()})
        db.add_event(self.run_id, "run_started", {})
        try:
            self._load_experiences()
            self._check_initial()
            if not self.stop_reason:
                self._reuse()
            while not self.stop_reason:
                self._iterate()
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
            self._stop("internal_error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-3000:]}")
        loop_elapsed = time.perf_counter() - self.t0
        db.update("runs", "run_id", self.run_id, {"loop_ended_at": db.now(), "stop_reason": self.stop_reason,
                                                  "stop_detail": self.stop_detail, "best_candidate_id": self.best_id})
        db.add_event(self.run_id, "loop_ended", {"stop_reason": self.stop_reason, "detail": self.stop_detail,
                                                 "loop_elapsed_s": round(loop_elapsed, 3), "best_candidate_id": self.best_id})
        try:
            self._final_evaluation()
        except Exception as exc:  # noqa: BLE001
            db.add_event(self.run_id, "final_eval_error", {"error": f"{type(exc).__name__}: {exc}"})
        if self.opts.mode == "learn":
            self._publish()
        status = {"user_stopped": "stopped", "environment_error": "failed", "internal_error": "failed",
                  "model_api_error": "failed"}.get(self.stop_reason, "completed")
        db.update("runs", "run_id", self.run_id, {"status": status, "ended_at": db.now()})
        rep = report.build(self.run_id)
        (self.dir / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2))
        db.add_event(self.run_id, "run_finished", {"status": status, "stop_reason": self.stop_reason,
                                                   "goal_met": rep["outcome"]["goal_met"]})
        return rep

    def _load_experiences(self) -> None:
        """Retrieve once per run from the fixed snapshot; the same records go into every request."""
        self.experiences, summary = memory.retrieve(self.snapshot_id, self.task.manifest["family"], self.task.dev_profile)
        self.experience_summary = summary
        for rank, e in enumerate(self.experiences, start=1):
            db.insert("run_experiences", {"run_id": self.run_id, "experience_id": e["experience_id"], "rank": rank,
                                          "matching_features": e["match"]["matching_features"]})
        db.update("runs", "run_id", self.run_id, {"retrieval_json": db.dumps(summary)})
        db.add_event(self.run_id, "experiences_loaded", {"snapshot_id": self.snapshot_id, **summary})

    def _publish(self) -> None:
        if self.stop_reason in NO_PUBLISH:
            db.add_event(self.run_id, "learning_skipped", {"reason": self.stop_reason})
            return
        try:
            snap = memory.publish(self.run_id)
        except Exception as exc:  # noqa: BLE001
            db.add_event(self.run_id, "learning_failed", {"error": f"{type(exc).__name__}: {exc}"})
            return
        if snap:
            db.update("runs", "run_id", self.run_id, {"published_snapshot_id": snap})

    def _check_initial(self) -> None:
        """The initial program is candidate c0: verified correct on dev, speedup 1.0 by definition."""
        code = self.task.initial_code
        cid = self._add_candidate(code, origin="initial", parent=None, model_call_id=None)
        started = db.now()
        ev = evaluator.evaluate(self.task, code.encode(), "dev", self.measure, self.limits,
                                run_id=self.run_id, candidate_id=cid, measure_timing=False)
        latest = {**ev.public_feedback(), "status": ev.status, "correct": ev.correct,
                  "speedup": 1.0 if ev.correct and self.task.target_min_speedup is not None else None,
                  "note": "initial program; measured score" if self.task.target_min_speedup is None else "initial program; speedup 1.0 by definition"}
        self.candidates[cid]["latest_evaluation"] = latest
        ok = ev.status == "passed"
        if ok:
            self.best_id = cid
        self._step("program", "run_validation", ev.status, started_at=started, candidate_id=cid, evaluation_id=ev.evaluation_id,
                   purpose="验证初始程序在开发数据上正确，作为基线候选",
                   result=ev.public_feedback(), next_decision="continue" if ok else "stop: environment_error")
        if not ok:
            self._stop("environment_error", f"initial program failed dev check: {ev.status} {ev.detail.get('failure')}")

    def _reuse(self) -> None:
        """Re-validate the closest verified programs from the snapshot before any model request (memory.REUSE).

        Eval runs stop here when one reaches the target. Learning runs raise their target above the best of them, so
        the model spends its requests on beating what is already known instead of re-deriving it."""
        if self.opts.research_mode != "legacy":
            return
        programs, summary = memory.reusable_programs(self.snapshot_id, self.task.manifest["family"], self.task.dev_profile)
        db.add_event(self.run_id, "reuse_selected", summary)
        if not programs:
            return
        target = self.task.target_min_speedup
        for i, prog in enumerate(programs):
            if db.one("SELECT stop_requested FROM runs WHERE run_id = ?", (self.run_id,))["stop_requested"]:
                return self._stop("user_stopped", "stop requested")
            remaining = self.limits.wall_clock_s - (time.perf_counter() - self.t0)
            if remaining < self.limits.min_request_window_s:
                break
            cid = self._add_candidate(prog["code"], origin="experience", parent="c0", model_call_id=None)
            differs = "、".join(f"{f}（经验 {d['experience']}，本任务 {d['current']}）" for f, d in prog["differs"].items()) or "无"
            self._step("program", "reuse_candidate", "submitted", candidate_id=cid,
                       purpose=f"复用经验 {prog['experience_id']} 中已验证的程序，不调用模型（第 {i + 1}/{len(programs)} 个）",
                       hypothesis=(f"该程序在 {prog['task_id']} 上实测 {prog['speedup']}×（{prog['successes']} 条成功记录）；本任务 "
                                   f"{prog['matching_features']}/{prog['of']} 项负载条件相同，不同项：{differs}。预计在本任务上仍正确且有改善"),
                       expected=f"正确，且全部样本快于基线、加速比 ≥ {target}",
                       verification=f"{self.task.presentation['validation']}，交替计时 {self.measure.repeats} 轮",
                       params={"experience_id": prog["experience_id"], "source_task_id": prog["task_id"],
                               "recorded_speedup": prog["speedup"], "matching_features": prog["matching_features"]},
                       next_decision="validate re-used program")
            ev = self._validate(cid)
            fb = ev.public_feedback()
            self.candidates[cid]["latest_evaluation"] = {k: fb.get(k) for k in ("status", "correct", "speedup", "improved", "goal_met", "failure", "timing_spread")}
            if ev.status in ("sandbox_error", "baseline_failed", "checker_error"):
                self._step("program", "run_validation", ev.status, candidate_id=cid, evaluation_id=ev.evaluation_id,
                           result=fb, next_decision="stop: environment_error")
                return self._stop("environment_error", f"evaluation of {cid}: {ev.status} {ev.detail.get('failure')}")
            replaced = self._recompute_best()
            last = i == len(programs) - 1
            self._step("program", "run_validation", ev.status, candidate_id=cid, evaluation_id=ev.evaluation_id,
                       result={**fb, "best_candidate_id": self.best_id, "best_replaced": replaced, "run_target_speedup": target},
                       next_decision="validate next re-used program" if not last else "re-use finished")
            db.add_event(self.run_id, "evaluation_finished", {"candidate_id": cid, "status": ev.status, "speedup": ev.speedup,
                                                              "goal_met": ev.goal_met, "best_candidate_id": self.best_id})
            self.last_feedback = {"validation_of": cid, **fb, "best_candidate_id": self.best_id}

        best = self.candidates[self.best_id].get("latest_evaluation") or {}
        reached = self.best_id != "c0" and best.get("improved") and (best.get("speedup") or 0) >= target
        if not reached:
            self.last_feedback = {"re_use": f"{len(programs)} verified program(s) from experience were re-validated on this task "
                                            "(origin 'experience' in Candidates); none reached the target",
                                  "best_candidate_id": self.best_id}
            return
        if self.opts.mode == "eval":
            return self._stop("goal_reached", f"re-used {self.best_id} dev speedup {best['speedup']} >= {target}; no model request needed")
        self.run_target = round(max(target, best["speedup"] * (1 + memory.REUSE["learn_target_margin"])), 4)
        self._step("program", "set_target", "done", candidate_id=self.best_id,
                   purpose=(f"学习运行：复用的 {self.best_id} 已达标（{best['speedup']}×），本次目标提高到超过它 "
                            f"{memory.REUSE['learn_target_margin']:.0%}，即 ≥ {self.run_target}×"),
                   result={"best_candidate_id": self.best_id, "best_dev_speedup": best["speedup"],
                           "task_target_speedup": target, "run_target_speedup": self.run_target},
                   next_decision="continue with the model to beat the best known program")
        db.add_event(self.run_id, "run_target_raised", {"from": target, "to": self.run_target, "best_candidate_id": self.best_id})
        self.last_feedback = {"re_use": f"re-validated program {self.best_id} already meets the task target; this learning run "
                                        f"only counts a candidate as on target at speedup >= {self.run_target}",
                              "best_candidate_id": self.best_id}

    def _on_target(self, ev: evaluator.Evaluation) -> bool:
        if self.task.objective["metric"] == "score":
            return bool(ev.status == "passed" and ev.goal_met)
        return bool(ev.status == "passed" and ev.improved and ev.speedup is not None and ev.speedup >= self.run_target)

    def _iterate(self) -> None:
        if db.one("SELECT stop_requested FROM runs WHERE run_id = ?", (self.run_id,))["stop_requested"]:
            return self._stop("user_stopped", "stop requested")
        blocked = self._budget_block()
        if blocked:
            return self._stop("budget_exhausted", blocked)
        if not self.opts.fixed_model and self.role == "small" and self.small_requests >= UPGRADE_RULE["max_small_requests_without_goal"]:
            self._upgrade(f"小模型已用 {self.small_requests} 次请求仍没有达标候选，按升级规则切换到大模型")

        started = db.now()
        res, call_id, cfg = self._call_model()
        if not res.ok:
            return self._handle_model_failure(res, call_id, cfg, started)
        self.api_errors_in_row = 0
        if self.opts.research_mode != "legacy" and time.perf_counter() >= self.t0 + self.limits.wall_clock_s:
            return self._stop("budget_exhausted", "model response completed after the research deadline")
        try:
            act = actions.parse(res.text or "")
        except actions.InvalidAction as exc:
            return self._invalid(started, call_id, exc, raw=res.text)

        handler = {
            "analyze": self._do_analyze, "get_evidence": self._do_evidence, "propose_candidate": self._do_propose,
            "run_validation": self._do_validate, "finish": self._do_finish,
        }[act.action]
        try:
            if self.opts.research_mode == "independent" and act.action not in ("propose_candidate", "finish"):
                raise actions.InvalidAction("independent_action", "independent attempts must propose a fresh candidate or finish")
            handler(act, call_id, started)
        except actions.InvalidAction as exc:
            self._invalid(started, call_id, exc, act=act)

    # ---------- model ----------

    def _budget_block(self) -> str | None:
        if self.requests_used >= self.limits.max_model_requests:
            return f"model_requests: used {self.requests_used}/{self.limits.max_model_requests}"
        remaining = self.limits.wall_clock_s - (time.perf_counter() - self.t0)
        if remaining < self.limits.min_request_window_s:
            return f"wall_clock: {remaining:.1f}s left, below the {self.limits.min_request_window_s:.0f}s request window"
        if self.limits.token_budget is not None and self.tokens_used >= self.limits.token_budget:
            return f"tokens: used {self.tokens_used}/{self.limits.token_budget}"
        return None

    def _budget_view(self) -> dict:
        elapsed = time.perf_counter() - self.t0
        visible_best = "c0" if self.opts.research_mode == "independent" else self.best_id
        best = self.candidates.get(visible_best or "", {}).get("latest_evaluation", {})
        return {
            "model_requests_used": self.requests_used, "model_requests_max": self.limits.max_model_requests,
            "candidates_used": self.model_candidates, "candidates_max": self.limits.max_candidates,
            "wall_clock_elapsed_s": round(elapsed, 1), "wall_clock_limit_s": self.limits.wall_clock_s,
            "current_model_role": self.role, "upgraded_to_large_model": self.role == "large",
            "best_candidate_id": visible_best, "best_dev_speedup": best.get("speedup"),
            "best_objective": best.get("objective"), "research_mode": self.opts.research_mode,
            "target_speedup": self.run_target, "task_target_speedup": self.task.target_min_speedup,
        }

    def _call_model(self) -> tuple[LLMResult, str, config.ModelConfig]:
        cfg = self.model_cfgs[self.role]
        independent = self.opts.research_mode == "independent"
        state = prompt.build_state(
            task=self.task,
            candidates=[{"candidate_id": cid, **c} for cid, c in self.candidates.items() if not independent or cid == "c0"],
            evidence=[] if independent else self.evidence, history=[] if independent else self.history,
            experiences=self.experiences, snapshot_id=self.snapshot_id,
            experience_summary=self.experience_summary,
            budget=self._budget_view(), last_feedback=None if independent else self.last_feedback,
        )
        remaining = self.limits.wall_clock_s - (time.perf_counter() - self.t0)
        timeout = max(1.0, min(self.limits.model_request_timeout_s, remaining))
        call_id = f"m{self.requests_used + 1}"
        db.add_event(self.run_id, "model_started", {"call_id": call_id, "role": self.role, "model": cfg.model, "timeout_s": round(timeout, 1)})
        started = db.now()
        res = self.clients[self.role].complete(self.system_prompt, state, actions.ACTION_SCHEMA, timeout, cfg.max_output_tokens)
        ended = db.now()
        self.requests_used += 1
        if self.role == "small":
            self.small_requests += 1
        cost, cost_status, price_version = estimate_cost(cfg.provider, cfg.model, res.usage,
                                                         res.error_kind not in NOT_BILLED_ERRORS, base_url=cfg.base_url)
        u = res.usage
        if u.input_tokens is not None and u.output_tokens is not None:
            self.tokens_used += u.input_tokens + u.output_tokens
        path = self.dir / "calls" / f"{call_id}.json"
        path.write_text(json.dumps({"request": res.request_body, "response": res.response_body,
                                    "system_prompt_sha256": self.system_prompt_sha}, ensure_ascii=False, indent=2, default=str))
        db.insert("model_calls", {
            "call_id": f"{self.run_id}/{call_id}", "run_id": self.run_id, "provider": cfg.provider, "role": self.role,
            "model_requested": cfg.model, "model_returned": res.model_returned, "reasoning_effort": cfg.reasoning_effort,
            "max_output_tokens": cfg.max_output_tokens, "status": "ok" if res.ok else "error",
            "error_kind": res.error_kind, "error_message": res.error_message, "request_id": res.request_id,
            "input_tokens": u.input_tokens, "cached_input_tokens": u.cached_input_tokens, "output_tokens": u.output_tokens,
            "reasoning_tokens": u.reasoning_tokens, "usage_source": u.source,
            "estimated_input_tokens": (len(self.system_prompt) + len(state)) // 4,
            "cost_usd": cost, "cost_status": cost_status, "price_version": price_version,
            "latency_s": round(res.latency_s, 3), "request_path": str(path), "response_path": str(path),
            "started_at": started, "ended_at": ended,
        })
        db.add_event(self.run_id, "model_finished", {
            "call_id": call_id, "role": self.role, "ok": res.ok, "error_kind": res.error_kind, "latency_s": round(res.latency_s, 2),
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens, "reasoning_tokens": u.reasoning_tokens,
            "cost_usd": cost, "cost_status": cost_status,
        })
        return res, call_id, cfg

    def _handle_model_failure(self, res: LLMResult, call_id: str, cfg: config.ModelConfig, started: str) -> None:
        kind = res.error_kind or "bad_response"
        is_api = kind in API_ERRORS
        self.api_errors_in_row = self.api_errors_in_row + 1 if is_api else 0
        fatal = kind in FATAL_API_ERRORS or self.api_errors_in_row >= MAX_CONSECUTIVE_API_ERRORS
        decision = "stop: model_api_error" if is_api and fatal else "retry with a new request if budget allows"
        self._step("model", "model_request", "api_error" if is_api else "unusable_reply", started_at=started,
                   model_call_id=call_id, result={"error_kind": kind, "message": res.error_message, "role": self.role},
                   next_decision=decision)
        if is_api and fatal:
            return self._stop("model_api_error", f"{cfg.provider}/{cfg.model}: {kind}: {res.error_message}")
        if not is_api:
            self.last_feedback = {"problem": kind, "message": res.error_message,
                                  "hint": "reply with one complete JSON action; keep it concise"}

    def _invalid(self, started: str, call_id: str, exc: actions.InvalidAction, act: actions.Action | None = None, raw: str | None = None) -> None:
        self._step("model", act.action if act else "invalid", "invalid_action", started_at=started, model_call_id=call_id,
                   purpose=act.purpose if act else None,
                   result={"kind": exc.kind, "message": str(exc), "raw_excerpt": (raw or "")[:500] or None},
                   next_decision="continue with feedback")
        self.last_feedback = {"problem": "invalid_action", "kind": exc.kind, "message": str(exc)}

    # ---------- actions ----------

    def _model_step(self, act: actions.Action, status: str, call_id: str, started: str, **kw) -> int:
        return self._step("model", act.action, status, started_at=started, model_call_id=call_id, purpose=act.purpose,
                          expected=act.expected_result, verification=act.verification, hypothesis=act.hypothesis,
                          params=act.params(), **kw)

    def _do_analyze(self, act: actions.Action, call_id: str, started: str) -> None:
        self._model_step(act, "done", call_id, started, result={"analysis": act.analysis}, next_decision="continue")
        self.last_feedback = None

    def _do_evidence(self, act: actions.Action, call_id: str, started: str) -> None:
        if self.task.is_native:
            raise actions.InvalidAction("unavailable_tool", "use native validation feedback for this benchmark; cProfile is unavailable")
        if act.tool not in actions.EVIDENCE_TOOLS:
            raise actions.InvalidAction("unknown_tool", f"tool must be one of {actions.EVIDENCE_TOOLS}")
        cid = self._existing_candidate(act.candidate_id, require_runnable=True)
        t_start, started_tool = time.perf_counter(), db.now()
        result = evaluator.profile_candidate(self.task, self.candidates[cid]["code"].encode(), self.measure, self.limits)
        tool_id = f"t{len(self.evidence) + 1}"
        path = self.dir / "tools" / f"{tool_id}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        db.insert("tool_calls", {
            "call_id": f"{self.run_id}/{tool_id}", "run_id": self.run_id, "tool": act.tool,
            "params_json": db.dumps({"candidate_id": cid, "dataset": "dev"}), "status": result["status"],
            "error_kind": None if result["status"] == "ok" else result["status"], "error_message": result.get("stderr_tail"),
            "duration_s": round(time.perf_counter() - t_start, 3), "output_path": str(path),
            "started_at": started_tool, "ended_at": db.now(),
        })
        seq = self._model_step(act, "done" if result["status"] == "ok" else "tool_failed", call_id, started, tool_call_id=tool_id,
                               candidate_id=cid, result={"tool": act.tool, "status": result["status"],
                                                         "output_correct": result["output_correct"]},
                               next_decision="continue")
        self.evidence.append({"tool": act.tool, "candidate_id": cid, "step": seq, "result": result})
        self.last_feedback = {"evidence": f"{act.tool} result for {cid} added under 'Evidence collected in this run'"}

    def _do_propose(self, act: actions.Action, call_id: str, started: str) -> None:
        if self.model_candidates >= self.limits.max_candidates:
            raise actions.InvalidAction("candidate_budget", "no candidate budget left")
        if self.opts.research_mode == "independent" and act.parent_candidate_id not in (None, "c0"):
            raise actions.InvalidAction("independent_parent", "independent attempts can only modify c0")
        parent = self._existing_candidate(act.parent_candidate_id or ("c0" if self.opts.research_mode == "independent" else self.best_id), require_runnable=False)
        static_error = None
        try:
            actions.check_code(act.code, self.limits.max_code_bytes, tuple(self.task.manifest.get("native", {}).get("allowed_imports", [])))
        except actions.InvalidAction as exc:
            if exc.kind in ("missing_code", "code_too_large"):
                raise
            static_error = exc  # a real but broken attempt: it consumes a candidate and counts as a miss
        self.model_candidates += 1
        cid = self._add_candidate(act.code or "", origin="model", parent=parent, model_call_id=call_id)
        self._model_step(act, "submitted", call_id, started, candidate_id=cid, result={"parent_candidate_id": parent},
                         next_decision="validate candidate")
        if static_error:
            ev = self._static_failure(cid, static_error)
        else:
            ev = self._validate(cid)
        self._after_validation(cid, ev, counts_as_attempt=True)

    def _do_validate(self, act: actions.Action, call_id: str, started: str) -> None:
        cid = self._existing_candidate(act.candidate_id, require_runnable=True)
        self._model_step(act, "requested", call_id, started, candidate_id=cid, next_decision="re-measure candidate")
        ev = self._validate(cid)
        self._after_validation(cid, ev, counts_as_attempt=False)

    def _do_finish(self, act: actions.Action, call_id: str, started: str) -> None:
        self._model_step(act, "done", call_id, started, result={"finish_reason": act.finish_reason}, next_decision="stop")
        self._stop("agent_finished", act.finish_reason or "model chose to finish")

    # ---------- validation & bookkeeping ----------

    def _validate(self, cid: str) -> evaluator.Evaluation:
        db.add_event(self.run_id, "evaluation_started", {"candidate_id": cid, "dataset": "dev"})
        return evaluator.evaluate(self.task, self.candidates[cid]["code"].encode(), "dev", self.measure, self.limits,
                                  run_id=self.run_id, candidate_id=cid,
                                  deadline=self.t0 + self.limits.wall_clock_s if self.opts.research_mode != "legacy" else None)

    def _static_failure(self, cid: str, exc: actions.InvalidAction) -> evaluator.Evaluation:
        ev = evaluator.Evaluation(uuid.uuid4().hex[:12], self.task.task_id, "dev", "static_check_failed", False,
                                  None, False, None, False, None, None, None,
                                  detail={"failure": {"category": exc.kind, "message": str(exc)}},
                                  started_at=db.now(), ended_at=db.now())
        db.insert("evaluations", {
            "evaluation_id": ev.evaluation_id, "run_id": self.run_id, "candidate_id": cid, "task_id": self.task.task_id,
            "dataset": "dev", "dataset_sha256": self.task.manifest["files"]["dev_input"]["sha256"], "status": ev.status,
            "executed": 0, "format_ok": None, "correct": 0, "improved": None, "goal_met": 0, "speedup": None,
            "candidate_median_s": None, "baseline_median_s": None, "detail_json": db.dumps(ev.detail),
            "evaluator_version": "static-check", "started_at": ev.started_at, "ended_at": ev.ended_at,
        })
        return ev

    def _after_validation(self, cid: str, ev: evaluator.Evaluation, counts_as_attempt: bool) -> None:
        fb = ev.public_feedback()
        eligible = self.opts.research_mode == "legacy" or time.perf_counter() <= self.t0 + self.limits.wall_clock_s
        fb["eligible_for_selection"] = eligible
        ev.detail["eligible_for_selection"] = eligible
        db.update("evaluations", "evaluation_id", ev.evaluation_id, {"detail_json": db.dumps(ev.detail)})
        self.candidates[cid]["latest_evaluation"] = fb
        if ev.status in ("sandbox_error", "baseline_failed", "checker_error"):
            self._step("program", "run_validation", ev.status, candidate_id=cid, evaluation_id=ev.evaluation_id,
                       result=fb, next_decision="stop: environment_error")
            return self._stop("environment_error", f"evaluation of {cid}: {ev.status} {ev.detail.get('failure')}")

        replaced = self._recompute_best()
        on_target = self._on_target(ev)
        if on_target and self.opts.research_mode == "legacy":
            decision = "stop: goal_reached"
        else:
            if counts_as_attempt:
                self.misses += 1
            decision = "continue"
            if not self.opts.fixed_model and self.role == "small" and self.misses >= UPGRADE_RULE["consecutive_misses"]:
                decision = ("upgrade to large model, continue" if self.requests_used < self.limits.max_model_requests
                            else "upgrade rule met but no model requests left")
        best = self.candidates[self.best_id].get("latest_evaluation") or {}
        progress = {"elapsed_s": round(time.perf_counter() - self.t0, 3), "best_candidate_id": self.best_id,
                    "metric": self.task.objective["metric"], "value": (best.get("objective") or {}).get("value")
                    if self.task.objective["metric"] == "score" else best.get("speedup"),
                    "model_requests": self.requests_used, "tokens": self.tokens_used}
        self._step("program", "run_validation", ev.status, candidate_id=cid, evaluation_id=ev.evaluation_id,
                   result={**fb, "best_candidate_id": self.best_id, "best_replaced": replaced, "run_target_speedup": self.run_target,
                           "progress": progress},
                   next_decision=decision)
        db.add_event(self.run_id, "evaluation_finished", {"candidate_id": cid, "status": ev.status, "speedup": ev.speedup,
                                                          "goal_met": ev.goal_met, "best_candidate_id": self.best_id})
        self.last_feedback = {"validation_of": cid, **fb, "best_candidate_id": self.best_id,
                              "run_target_speedup": self.run_target, "on_run_target": on_target}

        if not eligible or ev.status == "budget_exhausted":
            return self._stop("budget_exhausted", "development evaluation completed outside the research budget")
        if on_target and self.opts.research_mode == "legacy":
            return self._stop("goal_reached", f"{cid} dev speedup {ev.speedup} >= {self.run_target}")
        if decision.startswith("upgrade to"):
            self._upgrade(f"连续 {self.misses} 次候选未达到正确且达标，按升级规则切换到大模型")
        if self.model_candidates >= self.limits.max_candidates:
            return self._stop("budget_exhausted", f"candidates: used {self.model_candidates}/{self.limits.max_candidates}")

    def _recompute_best(self) -> bool:
        """Best = highest latest dev speedup among passed candidates whose improvement is beyond noise; else c0.

        Failed or regressed candidates stay on record but never displace the best artifact.
        """
        best, best_speedup = "c0", 1.0
        if self.task.objective["metric"] == "score":
            best_speedup = self.candidates["c0"]["latest_evaluation"]["objective"]["value"]
        for cid, c in self.candidates.items():
            latest = c.get("latest_evaluation") or {}
            value = (latest.get("objective") or {}).get("value") if self.task.objective["metric"] == "score" else latest.get("speedup")
            if (cid != "c0" and latest.get("status") == "passed" and latest.get("improved")
                    and latest.get("eligible_for_selection", True) and value is not None and value > best_speedup):
                best, best_speedup = cid, value
        changed = best != self.best_id
        self.best_id = best
        return changed

    def _upgrade(self, reason: str) -> None:
        if self.opts.fixed_model or self.requests_used >= self.limits.max_model_requests:
            return
        self.role = "large"
        detail = {"rule": UPGRADE_RULE["id"], "misses": self.misses, "small_requests": self.small_requests,
                  "to": self.model_cfgs["large"].model}
        self._step("program", "upgrade_model", "done", result=detail, next_decision="continue with large model", purpose=reason)
        db.add_event(self.run_id, "model_upgraded", detail)

    def _existing_candidate(self, cid: str | None, require_runnable: bool) -> str:
        if not cid or cid not in self.candidates:
            raise actions.InvalidAction("unknown_candidate", f"candidate {cid!r} does not exist; known: {list(self.candidates)}")
        if require_runnable and (self.candidates[cid].get("latest_evaluation") or {}).get("status") == "static_check_failed":
            raise actions.InvalidAction("candidate_not_runnable", f"candidate {cid} failed static checks")
        return cid

    def _add_candidate(self, code: str, origin: str, parent: str | None, model_call_id: str | None) -> str:
        cid = f"c{len(self.candidates)}"
        path = self.dir / "candidates" / f"{cid}.py"
        path.write_text(code)
        db.insert("candidates", {
            "run_id": self.run_id, "candidate_id": cid, "seq": len(self.candidates), "parent_candidate_id": parent,
            "origin": origin, "model_call_id": model_call_id, "code_path": str(path),
            "code_sha256": taskpkg.sha256_bytes(code.encode()), "created_at": db.now(),
        })
        self.candidates[cid] = {"origin": origin, "parent_candidate_id": parent, "code": code}
        db.add_event(self.run_id, "candidate_created", {"candidate_id": cid, "origin": origin, "parent_candidate_id": parent})
        return cid

    def _step(self, actor: str, action: str, status: str, *, started_at: str | None = None, purpose: str | None = None,
              expected: str | None = None, verification: str | None = None, hypothesis: str | None = None,
              params: dict | None = None, result: dict | None = None, next_decision: str | None = None,
              model_call_id: str | None = None, tool_call_id: str | None = None, candidate_id: str | None = None,
              evaluation_id: str | None = None) -> int:
        self.seq += 1
        db.insert("steps", {
            "step_id": f"{self.run_id}/s{self.seq}", "run_id": self.run_id, "seq": self.seq, "actor": actor, "action": action,
            "status": status, "purpose": purpose, "expected_result": expected, "verification": verification,
            "hypothesis": hypothesis, "params_json": db.dumps(params or {}), "result_json": db.dumps(result or {}),
            "next_decision": next_decision, "model_call_id": f"{self.run_id}/{model_call_id}" if model_call_id else None,
            "tool_call_id": f"{self.run_id}/{tool_call_id}" if tool_call_id else None, "candidate_id": candidate_id,
            "evaluation_id": evaluation_id, "started_at": started_at or db.now(), "ended_at": db.now(),
        })
        summary = {"step": self.seq, "actor": actor, "action": action, "status": status}
        if purpose:
            summary["purpose"] = purpose
        if candidate_id:
            summary["candidate_id"] = candidate_id
        if result and actor == "program":
            summary["result"] = {k: result.get(k) for k in ("status", "correct", "speedup", "objective", "goal_met", "best_candidate_id") if k in result}
        if self.opts.research_mode == "feedback" and actor == "model" and action == "analyze":
            summary["result"] = result
            if hypothesis:
                summary["hypothesis"] = hypothesis
        self.history.append(summary)
        db.add_event(self.run_id, "step", {**summary, "next_decision": next_decision})
        return self.seq

    def _stop(self, reason: str, detail: str) -> None:
        if not self.stop_reason:
            self.stop_reason, self.stop_detail = reason, detail

    # ---------- final ----------

    def _final_evaluation(self) -> None:
        if not self.opts.final_evaluation:
            db.add_event(self.run_id, "final_eval_skipped", {"reason": "development_only_protocol"})
            return
        if self.stop_reason in NO_FINAL_EVAL or not self.best_id:
            db.add_event(self.run_id, "final_eval_skipped", {"reason": self.stop_reason, "best_candidate_id": self.best_id})
            return
        cid = self.best_id
        db.add_event(self.run_id, "final_eval_started", {"candidate_id": cid})
        ev = evaluator.evaluate(self.task, self.candidates[cid]["code"].encode(), "final", self.measure, self.limits,
                                run_id=self.run_id, candidate_id=cid, measure_timing=cid != "c0")
        db.update("runs", "run_id", self.run_id, {"final_evaluation_id": ev.evaluation_id})
        db.add_event(self.run_id, "final_eval_finished", {"candidate_id": cid, "status": ev.status, "speedup": ev.speedup,
                                                          "goal_met": ev.goal_met})
