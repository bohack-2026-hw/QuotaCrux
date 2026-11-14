"""Runner contracts with fake HTTP and sandbox samples; no performance claims or paid requests."""

import copy
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from quotacrux import config, db, evaluator, report, routing_ablation, taskpkg
from quotacrux.agent import actions, routing, runner
from quotacrux.families import groupagg
from quotacrux.llm.base import LLMResult, Usage
from quotacrux.sandbox import executor


@pytest.fixture
def harness(monkeypatch):
    task = taskpkg.build_task("groupagg", {"task_id": "t-routing", "split": "smoke",
        "params": {"rows": 20, "keys": 3}, "dev_seed": 91, "final_seed": 92})
    monkeypatch.setattr(executor, "environment_info", lambda measure: {"image_id": "fake-routing-sandbox"})
    monkeypatch.setattr(executor, "run_sample", lambda code, input_bytes, *a, **kw:
                        executor.SampleResult("ok", 1.0, 0.0, 0, groupagg.reference_output(input_bytes), ""))
    monkeypatch.setattr(evaluator, "profile_candidate", lambda *a: {"status": "ok", "output_correct": True})

    class Harness:
        def __init__(self):
            self.task = task
            self.calls = []
            self.action_choices = ["propose_candidate", "propose_candidate", "finish"]
            self.model_choice = "large"
            self.generator_override = None
            self.decision_error = None
            self.stop_after_route = False
            self.decisions = []

        def clients(self, opts):
            owner = self
            count = 0

            class Client:
                def __init__(self, role):
                    self.role = role

                def complete(self, system, user, schema, timeout_s, max_output_tokens):
                    nonlocal count
                    count += 1
                    owner.calls.append({"role": self.role, "schema": schema, "state": user})
                    kind = owner.generator_override or ("propose_candidate" if count <= 2 else "finish")
                    act = actions.Action(kind, "test action", "test result", "dev evaluation",
                        code=task.initial_code + f"\n# candidate {count}\n" if kind == "propose_candidate" else None,
                        parent_candidate_id="c0", finish_reason="test complete" if kind == "finish" else None)
                    return LLMResult(True, json.dumps(asdict(act)), Usage(source="not_applicable"), 0.01,
                                     request_body={"state": user})

            return ({r: Client(r) for r in ("small", "large")},
                    {r: config.ModelConfig("scripted", f"scripted-{r}", r) for r in ("small", "large")})

        def decide(self, evidence, questions, timeout_s, *, model=None):
            q = questions[0]
            self.decisions.append({"evidence": evidence, "question": q})
            if self.stop_after_route:
                db.get().execute("UPDATE runs SET stop_requested = 1 WHERE status = 'running'")
            if self.decision_error:
                return LLMResult(False, None, Usage(), 0.1, error_kind=self.decision_error,
                                 error_message="fake decision failure")
            choice = self.action_choices.pop(0) if q["name"] == "action" else self.model_choice
            assert choice in {c["value"] for c in q["choices"]}
            answer = [{"type": "choice", "name": q["name"], "choice": choice, "confidence": 1.0,
                       "probabilities": [{"value": c["value"], "probability": float(c["value"] == choice)}
                                         for c in q["choices"]]}]
            return LLMResult(True, json.dumps(answer), Usage(100, 0, 0, 0, 0, "reported"), 0.1,
                             model_returned=model or routing.openai_decisions.MODEL,
                             request_body={"questions": questions}, response_body={"answers": answer})

        def run(self, action="llm", model="rule", **limits):
            r = runner.Runner(runner.RunOptions(task_id=task.task_id, snapshot_id="v0",
                router=False, routing=config.RoutingConfig(action, model),
                limits=replace(config.RunLimits(), **{"max_model_requests": 8, **limits})))
            r.create()
            return r.execute()

    h = Harness()
    monkeypatch.setattr(runner, "_make_clients", h.clients)
    monkeypatch.setattr(routing.openai_decisions, "decide", h.decide)
    monkeypatch.setattr(routing.typesafe_jev, "decide", h.decide)
    return h


@pytest.mark.parametrize("action,model,roles,routing_requests", [
    ("llm", "rule", ["small", "small", "large"], 0),
    ("decisions", "rule", ["small", "small"], 3),
    ("llm", "decisions", ["large", "large", "large"], 1),
    ("decisions", "decisions", ["large", "large"], 4),
    ("jev", "rule", ["small", "small"], 3),
    ("llm", "jev", ["large", "large", "large"], 1),
    ("jev", "jev", ["large", "large"], 4),
    ("jev", "decisions", ["large", "large"], 4),
    ("decisions", "jev", ["large", "large"], 4),
])
def test_four_routes_keep_evaluator_and_account_for_every_call(harness, action, model, roles, routing_requests):
    rep = harness.run(action, model)
    assert rep["stop_reason"] == "agent_finished", rep["stop_detail"]
    assert rep["outcome"]["final_correct"] and rep["outcome"]["best_is_initial"]
    assert [c["role"] for c in harness.calls] == roles
    assert rep["iterations"]["candidates_no_gain"] == 2
    assert rep["iterations"]["routing_requests"] == routing_requests
    assert rep["iterations"]["model_requests"] == len(roles) + routing_requests
    route_steps = [s for s in rep["steps"] if s["actor"] == "model" and s["action"] in ("route_action", "route_model")]
    assert len(route_steps) == routing_requests
    assert [s["model_role"] for s in route_steps] == [
        "router_action" if s["action"] == "route_action" else "router_model"
        for s in route_steps]
    ledger = rep["usage"]["by_purpose"]["routing"]
    assert ledger["input_tokens"] == routing_requests * 100
    jev_requests = (3 if action == "jev" else 0) + (1 if model == "jev" else 0)
    assert ledger["cost_usd"] == pytest.approx(round((routing_requests - jev_requests) * 0.00001
                                                    + jev_requests * 0.0000042, 6))
    assert rep["experience"]["published_snapshot_id"] is None
    if action in ("decisions", "jev"):
        assert all(c["schema"]["properties"]["action"]["enum"] == ["propose_candidate"] for c in harness.calls)


def test_decisions_model_router_can_stay_small_after_two_misses(harness):
    harness.model_choice = "small"
    rep = harness.run(model="decisions")
    assert rep["iterations"]["upgrades"] == 0
    assert [c["role"] for c in harness.calls] == ["small"] * 3
    assert rep["iterations"]["routing_requests"] == 3


@pytest.mark.parametrize("provider", ["decisions", "jev"])
def test_direct_actions_do_not_call_generation_or_model_router(harness, provider):
    harness.action_choices = ["profile_candidate:c0", "run_validation:c0", "finish"]
    rep = harness.run(provider, provider)
    assert rep["iterations"]["evidence_calls"] == 1
    assert rep["iterations"]["routing_requests"] == 3
    assert not harness.calls
    assert {d["question"]["name"] for d in harness.decisions} == {"action"}


@pytest.mark.parametrize("provider", ["decisions", "jev"])
def test_model_route_reserves_a_generation_request(harness, provider):
    rep = harness.run(model=provider, max_model_requests=1)
    assert rep["stop_reason"] == "budget_exhausted"
    assert not harness.calls and not harness.decisions


def test_action_choices_remove_generation_when_request_or_candidate_budget_is_empty(harness):
    harness.action_choices = ["finish"]
    rep = harness.run("decisions", "decisions", max_model_requests=1)
    assert rep["iterations"]["model_requests"] == 1
    assert not {"propose_candidate", "analyze"} & {c["value"] for c in harness.decisions[0]["question"]["choices"]}
    harness.action_choices = ["finish"]
    harness.run("decisions", max_candidates=0)
    choices = {c["value"] for c in harness.decisions[-1]["question"]["choices"]}
    assert "analyze" in choices and "propose_candidate" not in choices


@pytest.mark.parametrize("stop", ["tokens", "user"])
def test_stop_between_routing_and_generation(harness, stop):
    harness.stop_after_route = stop == "user"
    rep = harness.run("decisions", token_budget=100 if stop == "tokens" else None)
    assert rep["stop_reason"] == ("user_stopped" if stop == "user" else "budget_exhausted")
    assert rep["iterations"]["model_requests"] == 1 and not harness.calls


def test_generator_cannot_override_selected_action(harness):
    harness.generator_override = "finish"
    harness.action_choices = ["propose_candidate", "finish"]
    rep = harness.run("decisions")
    invalid = [s for s in rep["steps"] if s["status"] == "invalid_action"]
    assert len(invalid) == 1 and invalid[0]["result"]["kind"] == "route_mismatch"
    assert rep["iterations"]["candidates_proposed"] == 0
    assert rep["iterations"]["model_requests"] == 3


@pytest.mark.parametrize("error,count,status", [("timeout", 2, "unknown"), ("config", 1, "not_applicable")])
@pytest.mark.parametrize("provider", ["decisions", "jev"])
def test_decision_failures_are_recorded_without_generator_fallback(harness, error, count, status, provider):
    harness.decision_error = error
    rep = harness.run(model=provider)
    assert rep["status"] == "failed" and rep["stop_reason"] == "model_api_error"
    assert rep["iterations"]["routing_requests"] == count and not harness.calls
    assert rep["usage"]["by_purpose"]["routing"]["cost_status"] == status


def test_ablation_freezes_snapshot_and_detects_other_config_changes(harness, monkeypatch):
    harness.action_choices *= 2
    result = routing_ablation.execute([harness.task.task_id], "v0", limits=replace(config.RunLimits(), max_model_requests=8))
    assert result["status"] == "completed" and result["fair"]
    assert set(result["sides"]) == set(routing_ablation.VARIANTS)
    assert {s["routing_requests"] for s in result["sides"].values()} == {0, 1, 3, 4}
    assert json.loads(Path(result["artifact"]).read_text())["fair"]
    reports = {row["run_id"]: report.build(row["run_id"]) for row in result["runs"]}
    assert all(rep["config"]["router"]["version"] == "off" for rep in reports.values())
    assert len({r["config_fingerprint"] for r in reports.values()}) == 4
    changed = copy.deepcopy(result)
    changed["runs"][-1]["comparison_config"]["config"]["limits"]["max_candidates"] += 1
    monkeypatch.setattr(report, "build", lambda *a: pytest.fail("portable summary must not query the source database"))
    assert not routing_ablation.summarize(changed)["fair"]


def test_ablation_rotates_order_and_rejects_duplicate_tasks():
    rows = routing_ablation.plan(["a"], 4)
    assert len(rows) == 16
    assert {rows[i]["variant"] for i in (0, 4, 8, 12)} == set(routing_ablation.VARIANTS)
    with pytest.raises(ValueError):
        routing_ablation.plan(["a", "a"], 1)


@pytest.mark.parametrize("can_validate", [True, False])
def test_native_decision_menu_uses_objective_and_available_capabilities(can_validate):
    state = routing.RoutingState(system="native instructions", text="dev feedback", role="small",
        small_requests=0, misses=0, requests_remaining=20, candidates_remaining=10,
        runnable_candidates=("c0",), generation_requests=2, models={},
        objective={"metric": "score", "direction": "maximize"}, available_tools=(),
        can_validate=can_validate, research_mode="feedback")
    question = routing.DecisionsActionRouter().question(state)
    choices = {choice["value"] for choice in question["choices"]}
    assert "profile_candidate:c0" not in choices
    assert ("run_validation:c0" in choices) == can_validate
    assert {"finish", "analyze", "propose_candidate"} <= choices
    assert state.evidence()["objective"] == {"metric": "score", "direction": "maximize"}
    assert state.evidence()["available_tools"] == []
    assert state.evidence()["research_mode"] == "feedback"


def test_ablation_stops_and_saves_failed_run(harness):
    harness.decision_error = "config"
    result = routing_ablation.execute([harness.task.task_id], "v0")
    assert result["status"] == "failed" and not result["fair"]
    assert sum(bool(r.get("run_id")) for r in result["runs"]) == 2
    assert result["runs"][1]["stop_reason"] == "model_api_error"
    assert json.loads(Path(result["artifact"]).read_text())["status"] == "failed"


@pytest.mark.parametrize("provider", ["decisions", "jev"])
def test_api_accepts_routing_choices_and_rejects_unknown_ones(harness, monkeypatch, provider):
    from fastapi.testclient import TestClient
    from quotacrux import api

    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(api, "threading", SimpleNamespace(Thread=InlineThread))
    harness.action_choices = ["finish"]
    with TestClient(api.app) as client:
        body = {"task_id": harness.task.task_id, "snapshot_id": "v0", "action_router": provider, "model_router": provider}
        assert client.post("/api/runs", json={**body, "action_router": "unknown"}).status_code == 422
        response = client.post("/api/runs", json=body)
        assert response.status_code == 202
        rep = client.get(f"/api/runs/{response.json()['run_id']}").json()
        assert rep["status"] == "completed" and rep["iterations"]["routing_requests"] == 1
        assert rep["config"]["routing"]["action"] == provider
        assert rep["config"]["routing"]["model"] == provider
        assert f"--action-router {provider}" in rep["reproduce"]["run_again"]
        if provider == "jev":
            assert rep["config"]["routing"]["jev_model"] == "jev-1.14.0"
            call = db.one("SELECT * FROM model_calls WHERE run_id = ?", (rep["run_id"],))
            assert call["provider"] == "typesafe_jev" and call["model_returned"] == "jev-1.14.0"
            assert call["price_version"] == routing.typesafe_jev.PRICE_VERSION
