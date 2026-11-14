"""Native adaptive routing integration with fake providers and judges, never benchmark timing."""
from dataclasses import replace
import json
import time
import uuid

import pytest

from quotacrux import config, db, evaluator, routing_ablation
from quotacrux.agent import runner
from quotacrux.benchmarks import ale, algotune, native
from test_routing import harness
from test_research_protocol import score_task


@pytest.mark.parametrize("family,metric", [("ale-bench", "score"), ("algotune", "speedup")])
def test_native_four_way_batch_uses_adaptive_model_routing(harness, monkeypatch, family, metric):
    monkeypatch.setattr(ale, "environment_info", lambda *a: {"image_id": "fake-ale", "host": "desktop"})
    monkeypatch.setattr(algotune, "environment_info", lambda *a: {"image_id": "fake-algotune", "host": "mac"})
    task = native.package(family, "fixture", "smoke", {"revision": "fixture"}, "Optimize this program.",
        "print(0)\n", [{"id": "dev", "input": "1"}], [{"id": "final", "input": "final-secret"}],
        objective={"metric": metric, "direction": "maximize"}, settings={"size": 1}, task_id=f"native-routing-{family}")
    evaluated = []

    def evaluate(task, code, dataset, measure, limits, *, run_id, candidate_id, **kwargs):
        evaluated.append((run_id, candidate_id, dataset))
        value = {"c0": 10, "c1": 20, "c2": 30}[candidate_id]
        objective = {"metric": metric, "direction": "maximize", "value": value, "baseline": 10}
        ev = evaluator.Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "passed", True, True, True,
            value > 10, value > 10, value / 10 if metric == "speedup" else None, None, None,
            detail={"objective": objective})
        return native.persist(task, ev, code, db.now(), time.perf_counter(), run_id, candidate_id)

    monkeypatch.setattr(evaluator, "evaluate", evaluate)
    harness.action_choices *= 2
    measure = config.MeasureConfig(cpuset_cpus="2", function_warmups=3)
    out = routing_ablation.execute([task.task_id], "v0", research_mode="feedback", research_model_policy="adaptive",
        limits=replace(config.RunLimits(), max_model_requests=20, max_candidates=10, wall_clock_s=900), measure=measure)
    assert out["status"] == "completed" and out["fair"] is True
    assert out["study"] == "routing" and out["summary"]["planned"] == 4
    assert {r["mode"] for r in out["runs"]} == {"feedback"}
    expected_calls = {"baseline": (0, 3), "action_decisions": (3, 2), "model_decisions": (1, 3), "both_decisions": (4, 2)}
    for row in out["runs"]:
        cfg = row["comparison_config"]["config"]
        assert cfg["research_protocol"]["model_policy"] == "adaptive"
        assert cfg["research_protocol"]["fixed_model"] is None and cfg["router"]["version"] == "off"
        assert cfg["measure"] == measure.to_dict()
        counts = row["iterations"]
        routing_requests, generation_requests = expected_calls[row["variant"]]
        assert counts["routing_requests"] == routing_requests
        assert counts["generation_requests"] == generation_requests
        assert counts["model_requests"] == routing_requests + generation_requests
        assert row["usage_by_purpose"]["routing"]["requests"] == routing_requests
        assert counts["upgrades"] == 1
        assert counts["candidates_proposed"] == 2  # c1 already meets the milestone
        assert row["best_candidate_id"] == "c2" and row["final_status"] == "completed"
        assert [(cid, ds) for rid, cid, ds in evaluated if rid == row["run_id"] and ds == "final"] == [("c2", "final")]
        assert "--research-model-policy adaptive" in row["reproduce"]["run_again"]
        assert "--fixed-model" not in row["reproduce"]["run_again"]
        if row["routing"]["model"] == "decisions":
            assert counts["small_model_requests"] == 0 and counts["large_model_requests"] == generation_requests
            chosen = [s for s in row["routing_steps"] if s["action"] == "route_model"]
            assert chosen[0]["result"]["choice"] == "large"
            assert chosen[0]["result"]["answers"][0]["probabilities"]
    for decision in harness.decisions:
        assert decision["evidence"]["objective"]["metric"] == metric
        assert decision["evidence"]["research_mode"] == "feedback"
        assert decision["evidence"]["available_tools"] == []
        assert "final-secret" not in json.dumps(decision)
        assert not any(c["value"].startswith("profile_candidate") for c in decision["question"]["choices"])


@pytest.mark.parametrize("mode,fixed,snapshot", [("independent", None, "v0"), ("no_feedback", None, "v0"),
    ("feedback", "small", "v0"), ("feedback", None, "v999")])
def test_invalid_adaptive_protocol_is_rejected_before_clients(harness, monkeypatch, mode, fixed, snapshot):
    monkeypatch.setattr(runner, "_make_clients", lambda *a: pytest.fail("invalid protocol must not construct clients"))
    with pytest.raises(ValueError):
        runner.Runner(runner.RunOptions(task_id=harness.task.task_id, mode="eval", snapshot_id=snapshot,
            research_mode=mode, research_model_policy="adaptive", fixed_model=fixed))


def test_native_adaptive_jev_keeps_final_private_and_uses_native_menu(harness, score_task, monkeypatch):
    def evaluate(task, code, dataset, measure, limits, *, run_id, candidate_id, **kwargs):
        value = 10 + int(candidate_id[1:])
        ev = evaluator.Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "passed", True, True, True,
            value > 10, value > 10, None, None, None,
            detail={"objective": {"metric": "score", "direction": "maximize", "value": value, "baseline": 10}})
        return native.persist(task, ev, code, db.now(), time.perf_counter(), run_id, candidate_id)

    monkeypatch.setattr(evaluator, "evaluate", evaluate)
    run = runner.Runner(runner.RunOptions(task_id=score_task.task_id, snapshot_id="v0",
        research_mode="feedback", research_model_policy="adaptive", routing=config.RoutingConfig("jev", "jev"),
        limits=replace(config.RunLimits(), max_model_requests=8)))
    run.create()
    rep = run.execute()
    assert rep["status"] == "completed" and rep["stop_reason"] == "agent_finished"
    assert rep["iterations"]["routing_requests"] == 4 and rep["iterations"]["generation_requests"] == 2
    assert rep["iterations"]["upgrades"] == 1 and rep["outcome"]["final_correct"]
    assert rep["best_candidate"]["candidate_id"] == "c2"
    for decision in harness.decisions:
        assert "private sentinel" not in json.dumps(decision)
        assert decision["evidence"]["objective"]["metric"] == "score"
        assert decision["evidence"]["objective"]["direction"] == "maximize"
        assert not any(c["value"].startswith("profile_candidate") for c in decision["question"]["choices"])
