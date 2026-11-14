"""Frozen plan, cross-mode fairness and incomplete/failure accounting."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from routeevo import config, research_compare as rc


@pytest.fixture
def execution(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VAR_DIR", tmp_path)
    monkeypatch.setattr(rc.compare, "LOCK_PATH", tmp_path / "compare.lock")
    monkeypatch.setattr(rc.taskpkg, "load", lambda task_id: SimpleNamespace(
        task_id=task_id, family="ale-bench", objective={"metric": "score", "direction": "maximize"},
        presentation={"workload": task_id}))
    owner = SimpleNamespace(started=[], reports=[])

    class Runner:
        def __init__(self, opts):
            self.opts = opts
            self.dir = tmp_path / f"run-{len(owner.started)}"

        def create(self):
            owner.started.append(self.opts)
            return f"run-{len(owner.started)}"

        def execute(self):
            rep = deepcopy(owner.reports.pop(0)) if owner.reports else make_report()
            if isinstance(rep, BaseException):
                raise rep
            rep["task"]["task_id"] = self.opts.task_id
            rep["config"]["research_protocol"]["mode"] = self.opts.research_mode
            rep["config"]["prompt"]["system_sha256"] = self.opts.research_mode
            if not self.opts.final_evaluation:
                rep["final_evaluation"] = None
                rep["outcome"]["final_status"] = "disabled"
            return rep

    monkeypatch.setattr(rc, "Runner", Runner)
    return owner


def make_report(*, status="completed", final_status="completed", value=10, baseline=10, candidate="c0", cpu="2"):
    return {
        "status": status, "stop_reason": "agent_finished", "outcome": {"final_status": final_status},
        "task": {"task_id": "test", "family": "ale-bench", "objective": {"metric": "score", "direction": "maximize"}},
        "config": {"prompt": {"version": "v7", "system_sha256": "fixture"},
                   "research_protocol": {"mode": "feedback", "fixed_model": "small"},
                   "task_manifest_sha256": "immutable-task", "measure": {"cpuset_cpus": cpu},
                   "limits": {"wall_clock_s": 900}, "fingerprint": "ignored"},
        "environment": {"image_id": "immutable-image", "limits": {"cpuset_cpus": cpu}},
        "best_candidate": {"candidate_id": candidate, "dev_evaluations": [{"status": "passed", "correct": True,
            "objective": {"metric": "score", "value": value, "baseline": baseline}}]},
        "final_evaluation": {"status": "passed" if final_status == "completed" else "checker_error",
            "correct": final_status == "completed", "objective": {"value": value, "baseline": baseline}},
        "iterations": {"model_requests": 2, "candidates_proposed": 1, "candidates_passed": 1},
        "timing": {"wall_clock_total_s": 2.0},
        "usage": {"total": {"requests": 2, "input_tokens": 100, "output_tokens": 25,
            "input_tokens_unknown_calls": 0, "output_tokens_unknown_calls": 0}},
        "progress": [{"value": value, "usage": {"requests": 1, "input_tokens": 40, "output_tokens": 10}}],
    }


def pricing():
    return {"model": "fixed-qwen", "currency": "CNY", "unit": "per_1m_tokens",
            "input_per_1m": 3, "output_per_1m": 12, "source": "https://provider.example/prices",
            "retrieved_at": "2026-11-14T07:00:00Z"}


def test_plan_balances_three_modes_and_preserves_fi_alternation():
    rows = rc.make_plan(["a", "b"], 3, {"b": ["feedback", "independent", "no_feedback"]})
    assert len(rows) == 15
    assert [r["mode"] for r in rows if r["task_id"] == "a"] == ["feedback", "independent", "independent", "feedback", "feedback", "independent"]
    assert [r["mode"] for r in rows if r["task_id"] == "b"] == ["feedback", "no_feedback", "independent", "no_feedback", "independent", "feedback", "independent", "feedback", "no_feedback"]
    assert len({(r["task_id"], r["repeat"], r["mode"]) for r in rows}) == 15
    with pytest.raises(ValueError, match="all three"):
        rc.make_plan(["a"], 1, {"a": ["feedback", "no_feedback"]})


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.append(deepcopy(rows[0])),
    lambda rows: rows[-1].update(mode="legacy"),
    lambda rows: rows[-1].update(task_id="unregistered"),
    lambda rows: rows[-1].update(repeat=0),
    lambda rows: rows[-1].update(status="completed"),
])
def test_whole_plan_is_validated_before_any_runner(execution, mutate):
    rows = rc.make_plan(["a"], 3)
    mutate(rows)
    with pytest.raises(ValueError):
        rc.execute(["a"], limits=config.RunLimits(), plan=rows)
    assert execution.started == []


def test_wave_subset_retains_central_identity_and_unknown_fairness(execution):
    row = {"seq": 17, "task_id": "a", "repeat": 3, "mode": "no_feedback", "wave": 9, "worker": "desktop-b"}
    out = rc.execute(["a"], limits=config.RunLimits(), plan=[row], plan_id="formal-central-30")
    assert out["plan"] == [row]
    assert out["plan_id"] == "formal-central-30"
    assert out["runs"][0]["seq"] == 17 and out["runs"][0]["worker"] == "desktop-b"
    assert out["fair"] is None and out["status"] == "completed"
    assert out["runs"][0]["comparison_config"]["environment"]["limits"]["cpuset_cpus"] == "2"


def test_failure_keeps_planned_denominator_and_does_not_claim_completed(execution):
    execution.reports = [make_report(final_status="failed")]
    out = rc.execute(["a"], limits=config.RunLimits(), modes_by_task={"a": list(rc.MODES)})
    assert len(execution.started) == 1
    assert out["status"] == "interrupted" and out["fair"] is None
    assert [r["status"] for r in out["runs"]] == ["failed", "not_run", "not_run"]
    assert out["summary"]["planned"] == 3 and out["summary"]["not_run"] == 2
    assert all(p["status"] == "missing_or_failed" for p in out["summary"]["pairs"])
    assert json.loads(Path(out["path"]).read_text())["status"] == "interrupted"
    lock = rc.compare._try_lock()
    assert lock is not None
    lock.close()


def test_changed_affinity_is_retained_and_marks_fair_false(execution):
    execution.reports = [make_report(cpu="2"), make_report(cpu="4")]
    with pytest.raises(RuntimeError, match="configuration or environment changed"):
        rc.execute(["a"], limits=config.RunLimits())
    out = json.loads(next((config.VAR_DIR / "comparisons").glob("research-*.json")).read_text())
    assert out["fair"] is False and out["status"] == "interrupted"
    assert len(out["runs"]) == 2 and all(r["comparison_config"] for r in out["runs"])
    assert out["runs"][1]["comparison_config"]["environment"]["limits"]["cpuset_cpus"] == "4"


def test_c0_and_zero_score_are_retained_in_mode_and_pair_summaries(execution):
    execution.reports = [make_report(value=0, baseline=0), make_report(value=20, baseline=0, candidate="c1")]
    out = rc.execute(["a"], limits=config.RunLimits())
    assert out["fair"] is True
    groups = {g["mode"]: g for g in out["summary"]["tasks"][0]["modes"]}
    assert groups["feedback"]["c0_deliveries"] == 1
    assert groups["feedback"]["final_values"] == [0]
    assert groups["feedback"]["final_metric_median"] == 0
    assert out["summary"]["pairs"][0]["difference_a_minus_b"] == -20
    for r in out["runs"]:
        r["mode"] = "feedback" if r["mode"] == "independent" else "independent"
    rc.summarize(out)
    assert out["summary"]["pairs"][0]["relative_difference_over_b"] is None


def test_price_model_mismatch_rejected_before_runner(execution, monkeypatch):
    monkeypatch.setattr(config, "default_model_configs", lambda: {"small": SimpleNamespace(model="different-qwen")})
    with pytest.raises(ValueError, match="model differs"):
        rc.execute(["a"], limits=config.RunLimits(), pricing=pricing())
    assert execution.started == []


def test_frozen_currency_and_progress_cost_survive_export(execution, monkeypatch):
    monkeypatch.setattr(config, "default_model_configs", lambda: {"small": SimpleNamespace(model="fixed-qwen")})
    out = rc.execute(["a"], limits=config.RunLimits(), pricing=pricing())
    assert out["price_snapshot"] == pricing()
    for row in out["runs"]:
        assert row["cost"]["currency"] == "CNY" and row["cost"]["amount"] == pytest.approx(0.0006)
        assert row["progress"][0]["cost"]["amount"] == pytest.approx(0.00024)
    assert all(g["cost"]["status"] == "estimated" for g in out["summary"]["tasks"][0]["modes"])


def test_compare_lock_blocks_without_constructing_runner(execution):
    lock = rc.compare._try_lock()
    assert lock is not None
    try:
        with pytest.raises(RuntimeError, match="another comparison"):
            rc.execute(["a"], limits=config.RunLimits())
        assert execution.started == []
    finally:
        lock.close()


def test_failed_outcomes_remain_in_fair_configuration_comparison(execution):
    out = rc.execute(["a"], limits=config.RunLimits())
    out["runs"][0].update(status="failed", final_status="failed")
    out["runs"][0]["final_evaluation"].update(status="wrong_output", correct=False)
    rc.summarize(out)
    assert out["fair"] is True
    assert out["fairness"]["all_planned_runs_recorded"] is True
    assert out["fairness"]["all_planned_runs_completed"] is False
    group = next(g for g in out["summary"]["tasks"][0]["modes"] if g["mode"] == "feedback")
    assert group["planned"] == group["failed"] == 1
    assert group["final_values"] == [None] and group["final_correct"] == 0
    assert out["summary"]["pairs"][0]["status"] == "missing_or_failed"


def test_unexpected_execution_error_preserves_slot_and_releases_lock(execution):
    execution.reports = [RuntimeError("retained failure")]
    with pytest.raises(RuntimeError, match="retained failure"):
        rc.execute(["a"], limits=config.RunLimits())
    out = json.loads(next((config.VAR_DIR / "comparisons").glob("research-*.json")).read_text())
    assert out["runs"][0]["status"] == "interrupted"
    assert out["runs"][0]["run_id"] == "run-1"
    assert out["runs"][0]["final_status"] == "not_run"
    assert "retained failure" in out["runs"][0]["error"]
    assert out["runs"][1]["status"] == "not_run" and out["fair"] is None
    lock = rc.compare._try_lock()
    assert lock is not None
    lock.close()


def test_cli_infers_task_ids_from_frozen_plan(tmp_path, monkeypatch, capsys):
    from routeevo import cli
    path = tmp_path / "plan.json"
    plan = [{"seq": 11, "task_id": "a", "repeat": 3, "mode": "no_feedback", "wave": 6}]
    path.write_text(json.dumps({"runs": plan}))
    seen = {}
    def execute(task_ids, **kwargs):
        seen.update(task_ids=task_ids, **kwargs)
        return {"status": "fixture"}
    monkeypatch.setattr(rc, "execute", execute)
    cli.main(["research-compare", "--plan", str(path), "--plan-id", "central", "--cpuset-cpus", "4"])
    assert seen["task_ids"] == ["a"] and seen["plan"] == plan
    assert seen["plan_id"] == "central" and seen["measure"].cpuset_cpus == "4"
    assert json.loads(capsys.readouterr().out)["status"] == "fixture"
