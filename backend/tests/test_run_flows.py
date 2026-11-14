"""End-to-end flows with the scripted model and the real Docker sandbox (functional checks only)."""

from pathlib import Path

import pytest

from conftest import requires_docker

SCRIPTS = Path(__file__).parent / "fixtures" / "scripts"


@pytest.fixture(scope="module")
def task():
    from routeevo import taskpkg

    entry = {"task_id": "t-flow", "split": "smoke", "params": {"rows": 300000, "keys": 5000, "skew": 0.8}, "dev_seed": 1, "final_seed": 2}
    return taskpkg.build_task("groupagg", entry)


def run(task, script: str, **limits):
    import dataclasses

    from routeevo import config
    from routeevo.agent.runner import RunOptions, Runner

    # v0 holds no programs to re-use, so these flows exercise the model loop whatever earlier tests published; with the
    # router on, v0 would send every run straight to the large model, so these upgrade-rule flows switch it off
    r = Runner(RunOptions(task_id=task.task_id, snapshot_id="v0", script=SCRIPTS / f"{script}.json", router=False,
                          limits=dataclasses.replace(config.RunLimits(), **limits)))
    r.create()
    return r.execute()


@requires_docker
def test_success_flow(task):
    rep = run(task, "success")
    assert rep["stop_reason"] == "goal_reached"
    assert rep["outcome"]["goal_met"] and rep["best_candidate"]["candidate_id"] == "c1"
    assert rep["iterations"]["evidence_calls"] == 1


@requires_docker
def test_research_view_and_bundle(task, tmp_path):
    from routeevo import cli, narrative

    rep = run(task, "failure_upgrade")
    r = rep["research"]
    assert r["definition"]["budget"]["model_requests"] == rep["config"]["limits"]["max_model_requests"]
    assert r["definition"]["baseline"]["dev_median_s"] > 0
    # verdicts come from the evaluations, one per proposed candidate, in order
    assert [e["verdict"] for e in r["experiments"]] == ["untestable", "untestable", "supported"]
    assert r["verdicts"]["supported"] == 1 and r["verdicts"]["untestable"] == 2
    out = tmp_path / "bundle"
    cli.export_bundle(rep["run_id"], out, narrative.run_markdown(rep["run_id"]))
    names = {x.name for x in out.iterdir()}
    assert {"README.md", "report.json", "best.py", "candidates", "reproduce.sh"} <= names
    assert (out / "best.py").read_text() == (out / "candidates" / "c3.py").read_text()
    assert "## 研究任务" in (out / "README.md").read_text()


@requires_docker
def test_failures_keep_best_and_trigger_upgrade(task):
    rep = run(task, "failure_upgrade")
    statuses = [c["dev_evaluations"][-1]["status"] for c in rep["candidates"]]
    assert statuses == ["passed", "wrong_output", "static_check_failed", "passed"]
    assert rep["iterations"]["upgrades"] == 1
    upgrade = next(s for s in rep["steps"] if s["action"] == "upgrade_model")
    later_models = [s for s in rep["steps"] if s["actor"] == "model" and s["seq"] > upgrade["seq"]]
    assert later_models and all(s["model_call_id"] for s in later_models)
    assert rep["usage"]["by_model"].keys() == {"small:scripted:scripted-small", "large:scripted:scripted-large"}


@requires_docker
def test_budget_stop_reports_no_improvement(task):
    rep = run(task, "budget_requests")
    assert rep["stop_reason"] == "budget_exhausted" and "model_requests" in rep["stop_detail"]
    assert rep["outcome"]["best_is_initial"] and not rep["outcome"]["goal_met"]
    assert rep["iterations"]["invalid_actions"] == 1 and rep["iterations"]["candidates_no_gain"] == 1
    assert rep["iterations"]["upgrades"] == 1  # 3 small requests without an on-target candidate (rule v2)


@requires_docker
def test_consecutive_api_errors_stop_run(task):
    rep = run(task, "api_errors")
    assert rep["status"] == "failed" and rep["stop_reason"] == "model_api_error"
    assert rep["outcome"]["final_correct"] is True  # initial program still delivered and checked


@requires_docker
def test_runs_are_serial(task):
    from routeevo.agent.runner import RunBusy, RunOptions, Runner

    first = Runner(RunOptions(task_id=task.task_id, script=SCRIPTS / "api_errors.json"))
    first.create()
    try:
        with pytest.raises(RunBusy):
            Runner(RunOptions(task_id=task.task_id, script=SCRIPTS / "api_errors.json")).create()
    finally:
        first.execute()


@requires_docker
def test_learning_publishes_snapshot_and_rollback(task):
    from routeevo import memory, taskpkg
    from routeevo.agent.runner import RunOptions, Runner

    other = taskpkg.build_task("groupagg", {"task_id": "t-flow-b", "split": "B", "params": {"rows": 300000, "keys": 5000, "skew": 0.8},
                                            "dev_seed": 3, "final_seed": 4})
    with pytest.raises(ValueError, match="only"):
        Runner(RunOptions(task_id=other.task_id, mode="learn", script=SCRIPTS / "success.json"))

    start = memory.active_snapshot()
    learner = Runner(RunOptions(task_id=task.task_id, mode="learn", snapshot_id=start, script=SCRIPTS / "failure_upgrade.json",
                                  router=False))
    learner.create()
    rep = learner.execute()
    new = rep["experience"]["published_snapshot_id"]
    assert new and memory.active_snapshot() == new
    snap = memory.snapshot(new)
    assert snap["parent_snapshot_id"] == start
    added = {a["experience_id"]: a for a in snap["diff"]["added"]}
    assert sorted(a["outcome"] for a in added.values()) == ["failure", "failure", "success"]
    groupby_fail = next(e for e in snap["experiences"] if e["result"]["status"] == "wrong_output")
    assert "itertools.groupby" in groupby_fail["action"]["code_features"]["imports"]
    assert groupby_fail["source"]["run_id"] == rep["run_id"] and groupby_fail["source"]["evaluation_id"]

    # An eval run on a held-out task reads the new snapshot and records exactly what it read; nothing is published.
    ev = Runner(RunOptions(task_id=other.task_id, mode="eval", script=SCRIPTS / "api_errors.json"))
    ev.create()
    rep_b = ev.execute()
    assert rep_b["snapshot_id"] == new and rep_b["experience"]["published_snapshot_id"] is None
    read = {r["experience_id"] for r in rep_b["experience"]["read"]}
    assert read and read <= set(added)
    assert memory.active_snapshot() == new

    # Rollback: future runs read the old snapshot; the new one and its records remain.
    memory.activate(start, reason="test rollback")
    rb = Runner(RunOptions(task_id=other.task_id, mode="eval", script=SCRIPTS / "api_errors.json"))
    rb.create()
    rep_rb = rb.execute()
    assert rep_rb["snapshot_id"] == start
    assert {r["experience_id"] for r in rep_rb["experience"]["read"]} <= set(memory.snapshot_experience_ids(start))
    assert memory.snapshot(new)["experiences"]


@requires_docker
def test_comparison_is_fair_alternating_and_rejects_leaks(task):
    from routeevo import compare, memory, taskpkg

    held = taskpkg.build_task("groupagg", {"task_id": "t-cmp-c", "split": "C", "params": {"rows": 200000, "keys": 3000},
                                           "dev_seed": 5, "final_seed": 6})
    from routeevo import db

    new = db.one("SELECT snapshot_id FROM snapshots ORDER BY version DESC LIMIT 1")["snapshot_id"]
    assert memory.snapshot_experience_ids(new), "depends on the learning test having published a snapshot"
    with pytest.raises(ValueError, match="not held out"):
        compare.create([task.task_id], "v0", new, 1, None, None)

    assert [(p["task_id"], p["snapshot_id"]) for p in compare.plan(["x", "y"], "v0", "v1", 2)] == [
        ("x", "v0"), ("x", "v1"), ("y", "v1"), ("y", "v0"), ("x", "v1"), ("x", "v0"), ("y", "v0"), ("y", "v1")]

    cid = compare.create([held.task_id], "v0", new, 1, "test", str(SCRIPTS / "success.json"))
    s = compare.execute(cid)
    assert s["status"] == "completed" and s["finished_runs"] == 2 and s["fair"]
    assert set(s["sides"]) == {"v0", new} and all(side["runs"] == 1 for side in s["sides"].values())
    assert s["learning_cost"]["in_lineage"]
    reads = {snap: [r["experiences_read"] for r in v["runs"]] for snap, v in s["per_task"][held.task_id].items()}
    assert reads["v0"] == [0]


@requires_docker
def test_two_round_session(task):
    from routeevo import compare, memory, session, taskpkg

    learn_task = taskpkg.build_task("groupagg", {"task_id": "t-ses-a", "split": "A", "params": {"rows": 200000, "keys": 3000},
                                                 "dev_seed": 41, "final_seed": 42})
    unseen = taskpkg.build_task("groupagg", {"task_id": "t-ses-b", "split": "B", "params": {"rows": 200000, "keys": 4000},
                                             "dev_seed": 43, "final_seed": 44})
    with pytest.raises(ValueError):
        session.create(learn_task.task_id, learn_task.task_id, "v0")
    sid = session.create(learn_task.task_id, unseen.task_id, "v0")
    session.execute(sid, script=SCRIPTS / "success.json")
    s = session.get(sid)
    assert s["status"] == "completed" and s["phase"] == "done"
    assert memory.snapshot(s["new_snapshot_id"])["parent_snapshot_id"] == "v0"
    summary = compare.summarize(s["comparison_id"])
    assert summary["tasks"] == [unseen.task_id] and summary["finished_runs"] == 2 and summary["fair"]


@requires_docker
def test_small_model_stalling_triggers_upgrade(task):
    rep = run(task, "small_stalls")
    up = next(s for s in rep["steps"] if s["action"] == "upgrade_model")
    assert up["result"]["small_requests"] == 3 and up["result"]["rule"] == "upgrade-rule-v2"
    assert rep["stop_reason"] == "goal_reached" and rep["best_candidate"]["candidate_id"] == "c1"


@requires_docker
def test_reuse_skips_the_model_and_learning_raises_the_target():
    from routeevo import memory, taskpkg
    from routeevo.agent.runner import RunOptions, Runner

    params = {"rows": 300000, "keys": 5000, "skew": 0.8}
    learn_task = taskpkg.build_task("groupagg", {"task_id": "t-reuse-a", "split": "smoke", "params": params, "dev_seed": 51, "final_seed": 52})
    held = taskpkg.build_task("groupagg", {"task_id": "t-reuse-b", "split": "B", "params": params, "dev_seed": 53, "final_seed": 54})

    def go(task_id, mode, snapshot, script):
        r = Runner(RunOptions(task_id=task_id, mode=mode, snapshot_id=snapshot, script=SCRIPTS / f"{script}.json"))
        r.create()
        return r.execute()

    first = go(learn_task.task_id, "learn", "v0", "success")
    snap = first["experience"]["published_snapshot_id"]
    stored = memory.snapshot(snap)["experiences"]
    assert any(e["outcome"] == "success" and e["action"]["code"] for e in stored)
    assert first["iterations"]["programs_reused"] == 0  # v0 holds no programs

    # Eval: the verified program is re-validated by the program itself; any model request would be an API error.
    ev = go(held.task_id, "eval", snap, "api_errors")
    assert ev["stop_reason"] == "goal_reached" and ev["iterations"]["model_requests"] == 0
    assert ev["outcome"]["best_from_reuse"] and ev["outcome"]["goal_met"]
    exps = ev["research"]["experiments"]
    assert [(e["kind"], e["verdict"]) for e in exps] == [("reuse", "supported")]

    # Learn: re-use meets the task target, so the run raises its own target and asks the model to beat the program.
    again = go(learn_task.task_id, "learn", snap, "success")
    raised = next(s for s in again["steps"] if s["action"] == "set_target")
    assert again["run_target_speedup"] == raised["result"]["run_target_speedup"] > 1.10
    assert again["iterations"]["model_requests"] >= 1
    later = memory.snapshot(again["experience"]["published_snapshot_id"])["diff"]["added"]
    kinds = {memory.experience(a["experience_id"])["action"]["kind"] for a in later}
    assert "reuse_candidate" in kinds
