"""Shared-memory routing, paid Decisions routing and isolated research keep distinct protocols."""
from dataclasses import replace

import pytest

from quotacrux import config
from quotacrux.agent import routing, runner
from test_research_protocol import score_task, scripted_run
from test_routing import harness


NONDEFAULT_ROUTING = [config.RoutingConfig("decisions", "rule"),
                      config.RoutingConfig("llm", "decisions"),
                      config.RoutingConfig("decisions", "decisions")]


@pytest.mark.parametrize("selection", NONDEFAULT_ROUTING)
@pytest.mark.parametrize("context", ["feedback", "independent", "native-default", "native-legacy"])
def test_research_and_native_reject_decisions_before_client_creation(harness, score_task, monkeypatch, selection, context):
    task = score_task if context.startswith("native-") else harness.task
    mode = {"native-default": None, "native-legacy": "legacy"}.get(context, context)
    monkeypatch.setattr(runner, "_make_clients", lambda *args: pytest.fail("unsupported routing must fail before client creation"))
    with pytest.raises(ValueError, match="action_router=llm and model_router=rule"):
        runner.Runner(runner.RunOptions(task_id=task.task_id, snapshot_id="v0",
            research_mode=mode, routing=selection))
    assert not harness.calls and not harness.decisions


def execute(harness, **options):
    run = runner.Runner(runner.RunOptions(task_id=harness.task.task_id, snapshot_id="v0",
        limits=replace(config.RunLimits(), max_model_requests=8), **options))
    run.create()
    return run.execute()


@pytest.mark.parametrize("role", ["small", "large"])
@pytest.mark.parametrize("model_router", ["rule", "decisions"])
def test_fixed_model_skips_initial_router_paid_model_router_and_upgrade(harness, role, model_router):
    rep = execute(harness, router=True, fixed_model=role, routing=config.RoutingConfig("llm", model_router))
    assert rep["status"] == "completed" and rep["stop_reason"] == "agent_finished"
    assert rep["config"]["router"]["version"] == "off" and rep["route"] is None
    assert [call["role"] for call in harness.calls] == [role] * 3
    assert harness.decisions == []
    assert rep["iterations"]["upgrades"] == 0
    assert rep["iterations"]["routing_requests"] == 0
    assert rep["iterations"]["model_requests"] == rep["iterations"]["generation_requests"] == 3
    ledger = rep["usage"]["by_purpose"]["routing"]
    assert ledger["input_tokens"] == 0 and ledger["cost_usd"] == 0


def test_fixed_model_retains_requested_action_decisions_without_model_decision_charge(harness):
    rep = execute(harness, router=True, fixed_model="small", routing=config.RoutingConfig("decisions", "decisions"))
    assert rep["status"] == "completed" and rep["stop_reason"] == "agent_finished"
    assert [call["role"] for call in harness.calls] == ["small", "small"]
    assert [call["question"]["name"] for call in harness.decisions] == ["action"] * 3
    assert rep["iterations"]["upgrades"] == 0
    assert rep["iterations"]["routing_requests"] == 3
    assert rep["iterations"]["model_requests"] == 5
    ledger = rep["usage"]["by_purpose"]["routing"]
    assert ledger["input_tokens"] == 300 and ledger["cost_usd"] == pytest.approx(0.00003)


def test_legacy_model_decisions_gets_first_choice_even_with_empty_memory(harness):
    harness.model_choice = "small"
    rep = execute(harness, router=True, routing=config.RoutingConfig("llm", "decisions"))
    assert rep["status"] == "completed" and rep["stop_reason"] == "agent_finished"
    assert rep["config"]["router"]["version"] == "off"
    assert [call["role"] for call in harness.calls] == ["small"] * 3
    assert [call["question"]["name"] for call in harness.decisions] == ["model"] * 3
    assert rep["iterations"]["upgrades"] == 0
    assert rep["iterations"]["routing_requests"] == 3
    assert rep["iterations"]["model_requests"] == 6


def test_independent_research_keeps_history_private_and_adds_no_router_requests(score_task, tmp_path, monkeypatch):
    monkeypatch.setattr(routing.openai_decisions, "decide", lambda *args, **kwargs:
                        pytest.fail("independent research must not make Decisions requests"))
    rep, states = scripted_run(score_task, tmp_path, monkeypatch, "independent", analyze_first=True)
    assert rep["status"] == "completed" and rep["stop_reason"] == "agent_finished"
    assert len(states) == 4
    for state in states:
        assert all(secret not in state for secret in (
            "private sentinel", "candidate_secret_1", "candidate_secret_2", "analysis_secret", "hypothesis_secret"))
        assert "## Steps so far" not in state
        assert "Feedback on your previous reply" not in state
    assert rep["experience"]["read"] == [] and rep["route"] is None
    assert rep["iterations"]["upgrades"] == rep["iterations"]["routing_requests"] == 0
    assert rep["iterations"]["model_requests"] == rep["iterations"]["generation_requests"] == 4
    assert rep["usage"]["by_purpose"]["routing"]["cost_usd"] == 0
