"""Independent action and model routers; execution, validation and budgets belong to Runner."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol

from ..config import ModelConfig, RoutingConfig
from ..llm.base import LLMResult
from ..llm import openai_decisions
from . import actions

UPGRADE_RULE = {
    "id": "upgrade-rule-v2",
    "description": "start with the small model; switch to the large model for the rest of the run, if model requests "
                   "remain, after 2 consecutive candidate attempts that are not correct-and-on-target or after 3 small-model "
                   "requests without an on-target candidate",
    "consecutive_misses": 2,
    "max_small_requests_without_goal": 3,
}
ACTION_INSTRUCTIONS = (
    "Select the next action for this code optimization run, using the task, evidence and remaining budget. "
    "Prefer actions that can yield a correct candidate meeting the active speedup target. Tools and validation "
    "operate only on dev data. A generation action requires additional model requests; direct tool actions do not. "
    "Finish when further work is unlikely to help. Do not infer an unseen candidate's measured performance."
)
MODEL_INSTRUCTIONS = (
    "Choose which code-generating model should handle the pending request. Weigh progress, failed approaches, "
    "task difficulty and remaining budget against the extra cost and latency of the large model. The small model "
    "is the usual first choice; upgrade when the evidence warrants it. An upgrade is irreversible for this run. "
    "Choose independently of the fixed two-miss/three-small-request upgrade heuristic."
)
MODEL_QUESTION = {
    "type": "choice", "name": "model", "instructions": MODEL_INSTRUCTIONS,
    "choices": [{"value": "small", "description": "Continue using the small generation model."},
                {"value": "large", "description": "Upgrade to the large generation model."}],
}


@dataclass(frozen=True)
class RoutingState:
    system: str
    text: str
    role: str
    small_requests: int
    misses: int
    requests_remaining: int
    candidates_remaining: int
    runnable_candidates: tuple[str, ...]
    generation_requests: int
    models: dict

    def evidence(self) -> dict:
        return {"agent_instructions": self.system, "state": self.text, "generation_models": self.models,
                "small_requests": self.small_requests, "candidate_misses": self.misses,
                "generation_requests_needed": self.generation_requests}


@dataclass(frozen=True)
class ActionSelection:
    action: actions.Action | None = None
    generate: str | None = None
    choice: str | None = None


@dataclass(frozen=True)
class ModelSelection:
    role: str
    reason: str


class ActionRouter(Protocol):
    def config_for(self, role: str) -> ModelConfig: ...
    def request(self, state: RoutingState, timeout_s: float) -> LLMResult: ...
    def resolve(self, state: RoutingState, result: LLMResult) -> ActionSelection: ...


class ModelRouter(Protocol):
    eager_after_validation: bool
    def config_for(self, role: str) -> ModelConfig | None: ...
    def request(self, state: RoutingState, timeout_s: float) -> LLMResult: ...
    def resolve(self, state: RoutingState, result: LLMResult | None) -> ModelSelection: ...


class LLMActionRouter:
    def __init__(self, clients: dict, configs: dict[str, ModelConfig]):
        self.clients, self.configs = clients, configs

    def config_for(self, role: str) -> ModelConfig:
        return self.configs[role]

    def request(self, state: RoutingState, timeout_s: float) -> LLMResult:
        cfg = self.config_for(state.role)
        return self.clients[state.role].complete(state.system, state.text, actions.ACTION_SCHEMA, timeout_s, cfg.max_output_tokens)

    def resolve(self, state: RoutingState, result: LLMResult) -> ActionSelection:
        return ActionSelection(action=actions.parse(result.text or ""))


def decision_config(role: str) -> ModelConfig:
    return ModelConfig(provider="openai_decisions", model=openai_decisions.MODEL, role=role,
                       base_url=openai_decisions.ENDPOINT.removesuffix("/decisions"), max_output_tokens=0)


class DecisionsActionRouter:
    def config_for(self, role: str) -> ModelConfig:
        return decision_config("router_action")

    def question(self, state: RoutingState) -> dict:
        choices = [{"value": "finish", "description": "End the run and deliver the best verified candidate."}]
        if state.requests_remaining > state.generation_requests:
            choices.append({"value": "analyze", "description": "Ask the generation model for analysis; no tool execution."})
            if state.candidates_remaining > 0:
                choices.append({"value": "propose_candidate", "description": "Ask the generation model for a complete candidate, then validate it."})
        for cid in state.runnable_candidates:
            choices.extend([
                {"value": f"profile_candidate:{cid}", "description": f"Profile {cid} on dev data."},
                {"value": f"run_validation:{cid}", "description": f"Re-measure {cid} on dev data."},
            ])
        return {"type": "choice", "name": "action", "instructions": ACTION_INSTRUCTIONS, "choices": choices}

    def request(self, state: RoutingState, timeout_s: float) -> LLMResult:
        return openai_decisions.decide(state.evidence(), [self.question(state)], timeout_s)

    def resolve(self, state: RoutingState, result: LLMResult) -> ActionSelection:
        choice = json.loads(result.text)[0]["choice"]
        if choice in ("analyze", "propose_candidate"):
            return ActionSelection(generate=choice, choice=choice)
        purpose = f"Decisions 动作路由选择 {choice}"
        if choice == "finish":
            action = actions.Action("finish", purpose, "交付当前最佳已验证候选", "由既有评测器执行最终验收",
                                    finish_reason="Decisions action router selected finish")
        else:
            kind, cid = choice.split(":", 1)
            action = actions.Action("get_evidence" if kind == "profile_candidate" else "run_validation", purpose,
                                    "取得开发数据上的证据", "由既有工具和评测器检验", candidate_id=cid,
                                    tool="profile_candidate" if kind == "profile_candidate" else None)
        return ActionSelection(action=action, choice=choice)


class RuleModelRouter:
    eager_after_validation = True

    def config_for(self, role: str) -> None:
        return None

    def request(self, state: RoutingState, timeout_s: float) -> LLMResult:
        raise RuntimeError("rule router makes no model request")

    def resolve(self, state: RoutingState, result: LLMResult | None) -> ModelSelection:
        if state.role == "large":
            return ModelSelection("large", "already upgraded")
        if state.misses >= UPGRADE_RULE["consecutive_misses"]:
            return ModelSelection("large", f"连续 {state.misses} 次候选未达到正确且达标，按升级规则切换到大模型")
        if state.small_requests >= UPGRADE_RULE["max_small_requests_without_goal"]:
            return ModelSelection("large", f"小模型已用 {state.small_requests} 次请求仍没有达标候选，按升级规则切换到大模型")
        return ModelSelection("small", "upgrade thresholds not reached")


class DecisionsModelRouter:
    eager_after_validation = False

    def config_for(self, role: str) -> ModelConfig | None:
        return decision_config("router_model") if role == "small" else None

    def request(self, state: RoutingState, timeout_s: float) -> LLMResult:
        return openai_decisions.decide(state.evidence(), [MODEL_QUESTION], timeout_s)

    def resolve(self, state: RoutingState, result: LLMResult | None) -> ModelSelection:
        if state.role == "large":
            return ModelSelection("large", "already upgraded")
        choice = json.loads(result.text)[0]["choice"]
        return ModelSelection(choice, f"Decisions 模型路由选择 {choice}")


def make_routers(config: RoutingConfig, clients: dict, models: dict) -> tuple[ActionRouter, ModelRouter]:
    action = LLMActionRouter(clients, models) if config.action == "llm" else DecisionsActionRouter()
    model = RuleModelRouter() if config.model == "rule" else DecisionsModelRouter()
    return action, model


def manifest(config: RoutingConfig) -> dict:
    return {**config.to_dict(), "version": "routing-adapters-v1", "decision_model": openai_decisions.MODEL,
            "action_prompt_sha256": hashlib.sha256(ACTION_INSTRUCTIONS.encode()).hexdigest(),
            "model_prompt_sha256": hashlib.sha256(MODEL_INSTRUCTIONS.encode()).hexdigest(),
            "upgrade_is_irreversible": True, "budget_counts": "all routing and generation requests"}
