"""The ablation changes model visibility, never the real selector or result ledger."""
import copy
import json
import time
import uuid
from dataclasses import replace

import pytest

from quotacrux import config, db, evaluator
from quotacrux.agent import prompt
from quotacrux.agent.runner import Runner, RunOptions
from quotacrux.benchmarks import ale, native
from quotacrux.llm.scripted import ScriptedClient


@pytest.fixture
def task(monkeypatch):
    monkeypatch.setattr(ale, "environment_info", lambda *args: {"image_id": "fixture"})
    return native.package("ale-bench", "blind", "smoke", {"revision": "fixture"}, "Print an integer.",
                          "print(0)\n", [{"id": "dev", "input": "1"}], [{"id": "final", "input": "PRIVATE"}],
                          objective={"metric": "score", "direction": "maximize"}, settings={}, task_id="blind-fixture")


def action(kind, **params):
    return {"action": kind, "purpose": "实验目的", "expected_result": "预期", "verification": "裁判", **params}


def run_script(task, tmp_path, monkeypatch, decisions, *, mode="no_feedback", outcome="passed", final=False,
               recheck_initial=False, fail_final=False):
    path = tmp_path / "blind.json"
    path.write_text(json.dumps({"small": decisions}))
    states, routing_views = [], []
    with monkeypatch.context() as patch:
        patch.setattr(time, "perf_counter", lambda: 1000.0)
        complete, routing_state, initial = ScriptedClient.complete, Runner._routing_state, Runner._check_initial

        def capture(self, system, user, *args):
            states.append((system, user))
            return complete(self, system, user, *args)

        def capture_routing(self):
            state = routing_state(self)
            routing_views.append((copy.deepcopy(state.evidence()), state.runnable_candidates))
            return state

        def fixed_public_initial(self):
            initial(self)
            # The public baseline identity is held fixed in the counterfactual comparison.
            self.initial_feedback["evaluation_id"] = "public-initial-evaluation"

        seen_initial = False

        def evaluate(task, code, dataset, measure, limits, *, run_id, candidate_id, **kwargs):
            nonlocal seen_initial
            if dataset == "final" and fail_final:
                raise RuntimeError("final checker unavailable")
            status = outcome if candidate_id == "c1" else "passed"
            value = 20 if candidate_id == "c1" else 10 if candidate_id == "c0" else 5
            detail = {"objective": {"metric": "score", "direction": "maximize", "value": value, "baseline": 10}}
            if candidate_id == "c0":
                if seen_initial and recheck_initial:
                    detail["failure"] = {"message": "PRIVATE_RECHECK_TIMING_SENTINEL"}
                seen_initial = True
            if status != "passed":
                detail["failure"] = {"message": "SECRET_EXTERNAL_FAILURE"}
            ev = evaluator.Evaluation(uuid.uuid4().hex[:12], task.task_id, dataset, status, True,
                status == "passed", status == "passed", value > 10 and status == "passed",
                value > 10 and status == "passed", None, None, None, detail=detail)
            return native.persist(task, ev, code, db.now(), time.perf_counter(), run_id, candidate_id)

        patch.setattr(ScriptedClient, "complete", capture)
        patch.setattr(Runner, "_routing_state", capture_routing)
        patch.setattr(Runner, "_check_initial", fixed_public_initial)
        patch.setattr(evaluator, "evaluate", evaluate)
        runner = Runner(RunOptions(task_id=task.task_id, research_mode=mode, script=path, final_evaluation=final,
            limits=replace(config.RunLimits(), max_model_requests=12, max_candidates=10)))
        runner.create()
        rep = runner.execute()
    return rep, states, routing_views


@pytest.mark.parametrize("outcome", ["wrong_output", "timeout", "static_check_failed"])
def test_counterfactual_results_do_not_change_actual_model_inputs(task, tmp_path, monkeypatch, outcome):
    decisions = [action("analyze", analysis="模型自己的 timeout / score 推理应保留", hypothesis="自己的假设"),
                 action("propose_candidate", code="print(1)\n", parent_candidate_id="c0"),
                 action("run_validation", candidate_id="c1"),
                 action("propose_candidate", code="print(2)\n"),
                 action("finish", finish_reason="结束")]
    good, good_inputs, good_routes = run_script(task, tmp_path, monkeypatch, decisions)
    bad, bad_inputs, bad_routes = run_script(task, tmp_path, monkeypatch, decisions, outcome=outcome)
    assert good_inputs == bad_inputs
    assert good_routes == bad_routes
    assert good["best_candidate"]["candidate_id"] == "c1"
    assert bad["best_candidate"]["candidate_id"] == "c0"
    assert good["candidates"][1]["dev_evaluations"] != bad["candidates"][1]["dev_evaluations"]
    assert good["candidates"][2]["parent_candidate_id"] == bad["candidates"][2]["parent_candidate_id"] == "c0"
    assert "模型自己的 timeout / score 推理应保留" in good_inputs[-1][1]
    assert "自己的假设" in good_inputs[-1][1]
    assert good_routes[-1][1] == ("c0", "c1", "c2")
    assert '"best_candidate_id": null' in good_inputs[-1][1]
    assert "PRIVATE" not in good_inputs[-1][1]


def test_static_failure_revalidation_is_hidden_but_retained(task, tmp_path, monkeypatch):
    decisions = [action("propose_candidate", code="def broken(\n", parent_candidate_id="c0"),
                 action("run_validation", candidate_id="c1"), action("finish", finish_reason="结束")]
    rep, states, routes = run_script(task, tmp_path, monkeypatch, decisions)
    assert [e["status"] for e in rep["candidates"][1]["dev_evaluations"]] == ["static_check_failed", "static_check_failed"]
    for _, text in states[1:]:
        assert "def broken(" in text
        assert "static_check_failed" not in text and "candidate_not_runnable" not in text and "SyntaxError" not in text
    assert routes[-1][1] == ("c0", "c1")


def test_rechecking_c0_does_not_update_public_initial_conditions(task, tmp_path, monkeypatch):
    decisions = [action("run_validation", candidate_id="c0"), action("finish", finish_reason="结束")]
    rep, states, _ = run_script(task, tmp_path, monkeypatch, decisions, recheck_initial=True)
    assert "PRIVATE_RECHECK_TIMING_SENTINEL" not in states[-1][1]
    rows = db.all_rows("SELECT detail_json FROM evaluations WHERE run_id=?", (rep["run_id"],))
    assert any("PRIVATE_RECHECK_TIMING_SENTINEL" in row["detail_json"] for row in rows)


def test_protocol_errors_remain_visible(task, tmp_path, monkeypatch):
    _, states, _ = run_script(task, tmp_path, monkeypatch,
        [{"raw": json.dumps({"action": "analyze"})}, action("finish", finish_reason="结束")])
    assert "missing_field" in states[1][1] and "purpose" in states[1][1]


def test_feedback_control_still_receives_external_results(task, tmp_path, monkeypatch):
    decisions = [action("propose_candidate", code="print(1)\n", parent_candidate_id="c0"), action("finish", finish_reason="结束")]
    _, states, _ = run_script(task, tmp_path, monkeypatch, decisions, mode="feedback", outcome="wrong_output")
    assert "SECRET_EXTERNAL_FAILURE" in states[-1][1]


def test_final_exception_is_failed_after_frozen_selection(task, tmp_path, monkeypatch):
    decisions = [action("propose_candidate", code="print(1)\n", parent_candidate_id="c0"), action("finish", finish_reason="结束")]
    rep, states, _ = run_script(task, tmp_path, monkeypatch, decisions, final=True, fail_final=True)
    assert rep["status"] == "failed"
    assert rep["best_candidate"]["candidate_id"] == "c1"
    assert len(states) == 2
    events = db.all_rows("SELECT type FROM events WHERE run_id=? ORDER BY event_id", (rep["run_id"],))
    kinds = [e["type"] for e in events]
    assert kinds.index("loop_ended") < kinds.index("final_eval_started") < kinds.index("final_eval_error")


def test_research_prompt_menus_and_required_fields(task):
    independent = prompt.system_prompt(task, "independent")
    menu = independent.split("Actions (", 1)[1].split("Every action", 1)[0]
    assert "propose_candidate" in menu and "finish" in menu
    assert "- analyze" not in menu and "- run_validation" not in menu and "- get_evidence" not in menu
    for mode in ("feedback", "no_feedback", "independent"):
        system = prompt.system_prompt(task, mode)
        examples = system.split("JSON examples (replace the values; return ONE object):\n", 1)[1].splitlines()
        objects = [json.loads(line) for line in examples]
        assert all(all(o[k] for k in ("purpose", "expected_result", "verification")) for o in objects)
        assert {o["action"] for o in objects} == ({"propose_candidate", "finish"} if mode == "independent"
                                                  else {"propose_candidate", "analyze", "finish"})
