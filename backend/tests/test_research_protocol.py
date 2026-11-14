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


def scripted_run(task, tmp_path, monkeypatch, mode, *, late=False, analyze_first=False, measure=None):
    path = tmp_path / "actions.json"
    decisions = [{"action": "propose_candidate", "purpose": "试验", "expected_result": "提高分数",
        "verification": "裁判", "code": f"print({n}) # candidate_secret_{n}\n", "parent_candidate_id": "c0"}
        for n in (1, 2)]
    if analyze_first:
        decisions.insert(0, {"action": "analyze", "purpose": "分析初始程序", "expected_result": "提出可检验的改动",
            "verification": "下一候选的裁判反馈", "analysis": "analysis_secret: 修改输出以提高分数",
            "hypothesis": "hypothesis_secret: 分数可能随输出增加"})
    path.write_text(json.dumps({"small": decisions}))
    states = []
    complete = ScriptedClient.complete

    def capture(self, system, user, *args):
        states.append(user)
        return complete(self, system, user, *args)

    monkeypatch.setattr(ScriptedClient, "complete", capture)
    runner = Runner(RunOptions(task_id=task.task_id, research_mode=mode, script=path, final_evaluation=False,
        measure=measure or config.MeasureConfig(),
        limits=replace(config.RunLimits(), max_model_requests=4 if analyze_first else 3, max_candidates=3)))

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
    measure = config.MeasureConfig(cpuset_cpus="2", function_warmups=3)
    rep, states = scripted_run(score_task, tmp_path, monkeypatch, mode, measure=measure)
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
    assert rep["config"]["measure"] == measure.to_dict()
    for command in ("run_again", "recheck_best"):
        assert "--cpuset-cpus 2" in rep["reproduce"][command]
        assert "--function-warmups 3" in rep["reproduce"][command]
    markdown = narrative.run_markdown(rep["run_id"])
    assert "None×" not in markdown and "原始得分" in markdown


@pytest.mark.parametrize("mode", ["feedback", "independent"])
def test_analysis_reaches_following_requests_only_in_feedback(score_task, tmp_path, monkeypatch, mode):
    rep, states = scripted_run(score_task, tmp_path, monkeypatch, mode, analyze_first=True)
    assert rep["stop_reason"] == "agent_finished"
    assert len(states) == 4
    assert "analysis_secret" not in states[0] and "hypothesis_secret" not in states[0]
    for state in states[1:]:
        assert ("analysis_secret: 修改输出以提高分数" in state) == (mode == "feedback")
        assert ("hypothesis_secret: 分数可能随输出增加" in state) == (mode == "feedback")
    if mode == "feedback":
        history = states[1].split("## Steps so far\n")[1].split("\n## ")[0]
        analysis = next(json.loads(line) for line in history.strip().splitlines()
                        if json.loads(line)["action"] == "analyze")
        assert analysis["result"]["analysis"] == "analysis_secret: 修改输出以提高分数"
        assert analysis["hypothesis"] == "hypothesis_secret: 分数可能随输出增加"
    else:
        rejected = next(step for step in rep["steps"] if step["action"] == "analyze")
        assert rejected["status"] == "invalid_action"
        assert rejected["result"]["kind"] == "independent_action"


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
