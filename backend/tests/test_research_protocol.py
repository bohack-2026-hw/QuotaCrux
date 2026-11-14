"""Protocol invariants with scripted decisions; native containers are checked separately."""
import json
import time
import uuid
from dataclasses import replace

import pytest

from routeevo import config, db, evaluator, narrative
from routeevo.agent.runner import RunOptions, Runner
from routeevo.benchmarks import ale, native
from routeevo.llm.scripted import ScriptedClient


@pytest.fixture
def score_task(monkeypatch):
    monkeypatch.setattr(ale, "environment_info", lambda *args: {"image_id": "test-only"})
    return native.package("ale-bench", "test", "smoke", {"revision": "fixture"}, "Print a feasible solution.",
        "print(0)\n", [{"id": "dev", "input": "1"}], [{"id": "private", "input": "private sentinel"}],
        objective={"metric": "score", "direction": "maximize"}, settings={}, task_id="native-protocol-fixture")


def scripted_run(task, tmp_path, monkeypatch, mode, *, late=False):
    path = tmp_path / "actions.json"
    path.write_text(json.dumps({"small": [{"action": "propose_candidate", "purpose": "试验", "expected_result": "提高分数",
        "verification": "裁判", "code": f"print({n}) # candidate_secret_{n}\n", "parent_candidate_id": "c0"}
        for n in (1, 2)]}))
    states = []
    complete = ScriptedClient.complete

    def capture(self, system, user, *args):
        states.append(user)
        return complete(self, system, user, *args)

    monkeypatch.setattr(ScriptedClient, "complete", capture)
    runner = Runner(RunOptions(task_id=task.task_id, research_mode=mode, script=path, final_evaluation=False,
        limits=replace(config.RunLimits(), max_model_requests=3, max_candidates=3)))

    def evaluate(task, code, dataset, measure, limits, *, run_id, candidate_id, **kwargs):
        value = {"c0": 10, "c1": 20, "c2": 30}[candidate_id]
        ev = evaluator.Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, "passed", True, True, True,
            value > 10, value > 10, None, None, None,
            detail={"objective": {"metric": "score", "direction": "maximize", "value": value, "baseline": 10}})
        if late and candidate_id == "c2":
            runner.t0 = time.perf_counter() - runner.limits.wall_clock_s - 1
        return native.persist(task, ev, code, db.now(), time.perf_counter(), run_id, candidate_id)

    monkeypatch.setattr(evaluator, "evaluate", evaluate)
    runner.create()
    return runner.execute(), states


@pytest.mark.parametrize("mode", ["feedback", "independent"])
def test_research_continues_and_selects_raw_score(score_task, tmp_path, monkeypatch, mode):
    rep, states = scripted_run(score_task, tmp_path, monkeypatch, mode)
    assert rep["status"] == "completed" and rep["stop_reason"] == "agent_finished"
    assert rep["iterations"]["candidates_proposed"] == 2  # c1 met the old stopping threshold
    assert rep["best_candidate"]["candidate_id"] == "c2"
    assert [p["value"] for p in rep["progress"]] == [20, 30]
    assert rep["iterations"]["upgrades"] == 0 and rep["experience"]["read"] == []
    assert rep["final_evaluation"] is None
    assert all("private sentinel" not in state for state in states)
    assert ("candidate_secret_1" in states[1]) == (mode == "feedback")
    assert ("Feedback on your previous reply" in states[1]) == (mode == "feedback")
    assert ("Steps so far" in states[1]) == (mode == "feedback")
    assert "--dev-only" in rep["reproduce"]["run_again"]
    assert f"--research-mode {mode}" in rep["reproduce"]["run_again"]
    markdown = narrative.run_markdown(rep["run_id"])
    assert "None×" not in markdown and "原始得分" in markdown


def test_late_better_score_cannot_replace_deliverable(score_task, tmp_path, monkeypatch):
    rep, _ = scripted_run(score_task, tmp_path, monkeypatch, "feedback", late=True)
    assert rep["stop_reason"] == "budget_exhausted"
    assert rep["best_candidate"]["candidate_id"] == "c1"
    assert rep["progress"][-1]["value"] == 20
    assert rep["candidates"][-1]["dev_evaluations"][-1]["eligible_for_selection"] is False
    assert rep["iterations"]["candidates_improved"] == 1


def test_research_rejects_cross_session_memory(score_task):
    with pytest.raises(ValueError, match="empty snapshot"):
        Runner(RunOptions(task_id=score_task.task_id, research_mode="feedback", snapshot_id="v999"))
    with pytest.raises(ValueError, match="eval mode"):
        Runner(RunOptions(task_id=score_task.task_id, research_mode="feedback", mode="learn"))


def test_kernel_reference_verified_before_remote_execution(tmp_path, monkeypatch):
    from routeevo.benchmarks import kernelbench
    source = tmp_path / "reference.py"
    source.write_text("untrusted source")
    monkeypatch.setattr(kernelbench, "call_worker", lambda *a: pytest.fail("must reject before SSH"))
    with pytest.raises(ValueError, match="pinned upstream blob"):
        kernelbench.import_problem("1_Square_matrix_multiplication_", split="smoke", source=source,
            worker_command='["ssh", "desktop", "python3", "worker.py"]', image="sha256:fixture")


def test_pair_fairness_keeps_budget_and_environment():
    from routeevo.research_compare import comparable
    import copy
    first = {"config": {"prompt": {"version": "v4", "system_sha256": "a"},
        "research_protocol": {"mode": "feedback", "fixed_model": "small"}, "limits": {"wall_clock_s": 900},
        "task_manifest_sha256": "task", "fingerprint": "ignored"}, "environment": {"image_id": "pinned"}}
    second = copy.deepcopy(first)
    second["config"]["prompt"]["system_sha256"] = "b"
    second["config"]["research_protocol"]["mode"] = "independent"
    assert comparable(first) == comparable(second)
    second["config"]["limits"]["wall_clock_s"] = 1800
    assert comparable(first) != comparable(second)
    second = copy.deepcopy(first)
    second["environment"]["image_id"] = "changed"
    assert comparable(first) != comparable(second)
