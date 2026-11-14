"""Router, online mode and the online stream, with scripted models and the real Docker sandbox (functional checks only)."""

from pathlib import Path

import pytest

from conftest import requires_docker

SCRIPTS = Path(__file__).parent / "fixtures" / "scripts"
LOG = {"rows": 60000, "endpoints": 60, "hours": 6, "order": "time", "error_rate": 0.02}
LOG_SHIFTED = {"rows": 60000, "endpoints": 3000, "hours": 40, "order": "shuffled", "error_rate": 0.1}
IV = {"rows": 150000, "value_max": 5_000_000, "length_mean": 30}


def build(task_id, family, split, params, seed):
    from quotacrux import taskpkg

    return taskpkg.build_task(family, {"task_id": task_id, "split": split, "family": family, "params": params,
                                       "dev_seed": seed, "final_seed": seed + 1})


def go(task_id, mode, snapshot, script, router=True):
    from quotacrux.agent.runner import RunOptions, Runner

    r = Runner(RunOptions(task_id=task_id, mode=mode, snapshot_id=snapshot, script=SCRIPTS / f"{script}.json", router=router))
    r.create()
    return r.execute()


@pytest.fixture(scope="module")
def tasks():
    return {
        "log_a": build("t-log-a", "logstats", "T", LOG, 301),
        "log_b": build("t-log-b", "logstats", "T", LOG, 303),
        "log_held": build("t-log-held", "logstats", "B", LOG, 305),
        "log_shift": build("t-log-shift", "logstats", "T", LOG_SHIFTED, 307),
        "iv_a": build("t-iv-a", "intervals", "T", IV, 311),
        "iv_b": build("t-iv-b", "intervals", "T", IV, 313),
    }


@requires_docker
def test_new_family_goes_to_the_large_model_and_online_memory_serves_the_next_task(tasks):
    from quotacrux import memory

    # 1. Nothing in v0 covers access logs: the router starts on the large model; online mode publishes what it verified.
    first = go("t-log-a", "online", "v0", "large_logstats")
    assert first["route"]["reason"] == "new_family" and first["route"]["route"] == "large"
    assert first["iterations"]["large_model_requests"] == 1 and first["iterations"]["small_model_requests"] == 0
    assert first["iterations"]["upgrades"] == 0 and first["outcome"]["goal_met"]
    s1 = first["experience"]["published_snapshot_id"]
    assert s1 and memory.active_snapshot() == s1
    assert any(e["outcome"] == "success" and e["conditions"]["family"] == "logstats" for e in memory.snapshot(s1)["experiences"])

    # 2. A similar log: the verified program is re-validated and delivered; any model request would be an API error.
    second = go("t-log-b", "online", s1, "api_errors")
    assert second["iterations"]["model_requests"] == 0 and second["outcome"]["goal_met"] and second["outcome"]["best_from_reuse"]
    assert second["route"] is None and second["stop_reason"] == "goal_reached"
    s2 = second["experience"]["published_snapshot_id"]
    kinds = {memory.experience(e)["action"]["kind"] for e in second["experience"]["published_experiences"]}
    assert s2 and kinds == {"reuse_candidate"}

    # 3. Eval reads the same memory but writes nothing.
    held = go("t-log-held", "eval", s2, "api_errors")
    assert held["outcome"]["goal_met"] and held["iterations"]["model_requests"] == 0
    assert held["experience"]["published_snapshot_id"] is None

    # 4. A learning run on a covered workload: re-use meets the target, the target is raised, and because similar
    #    successes exist the router starts on the small model.
    learn = go("t-log-b", "learn", s2, "large_logstats")
    assert learn["run_target_speedup"] > 1.10
    assert learn["route"]["reason"] == "familiar" and learn["route"]["route"] == "small"
    assert learn["iterations"]["small_model_requests"] >= 1


@requires_docker
def test_family_records_without_a_similar_success_route_as_new_conditions(tasks):
    from quotacrux import memory

    first = go("t-iv-a", "online", "v0", "large_intervals_same")
    assert first["route"]["reason"] == "new_family"
    s1 = first["experience"]["published_snapshot_id"]
    outcomes = {e["outcome"] for e in memory.snapshot(s1)["experiences"] if e["conditions"]["family"] == "intervals"}
    assert outcomes == {"no_gain"}
    # The family is known but nothing similar succeeded: straight to the large model again, with the reason recorded.
    second = go("t-iv-b", "eval", s1, "large_intervals_same")
    assert second["route"]["reason"] == "new_conditions" and second["route"]["family_records"] >= 1
    assert second["route"]["similar_successes"] == 0 and second["iterations"]["small_model_requests"] == 0
    # Experience of another family never counts: groupagg records do not make access logs familiar.
    assert memory.retrieve(s1, "logstats", tasks["log_a"].dev_profile)[1]["family_records"] == 0


@requires_docker
def test_router_off_always_starts_small(tasks):
    rep = go("t-log-shift", "eval", "v0", "large_logstats", router=False)
    assert rep["route"]["reason"] == "router_off" and rep["iterations"]["small_model_requests"] >= 1
    assert rep["config"]["router"]["version"] == "off"
    on = go("t-log-shift", "eval", "v0", "large_logstats")
    assert on["config_fingerprint"] != rep["config_fingerprint"]


@requires_docker
def test_held_out_tasks_cannot_write_and_streams_need_learnable_tasks(tasks):
    from quotacrux import compare
    from quotacrux.agent.runner import RunOptions, Runner

    with pytest.raises(ValueError):
        Runner(RunOptions(task_id="t-log-held", mode="online"))
    with pytest.raises(ValueError):
        compare.create_stream(["t-log-held"], "v0", 1, None, None)
    with pytest.raises(ValueError):
        compare.create_stream(["t-log-a", "t-log-a"], "v0", 1, None, None)


@requires_docker
def test_stream_memory_arm_pays_once_and_restores_the_pointer(tasks):
    from quotacrux import compare, memory
    from quotacrux.narrative import evolution_note

    a = build("t-str-1", "logstats", "T", LOG, 321).task_id
    b = build("t-str-2", "logstats", "T", LOG, 323).task_id
    before = memory.active_snapshot()
    cid = compare.create_stream([a, b], "v0", 1, "test stream", str(SCRIPTS / "large_logstats.json"))
    s = compare.execute(cid)
    assert s["kind"] == "stream" and s["finished_runs"] == 4 and s["fair"] and not s["errors"]
    m, f = s["sides"]["memory"], s["sides"]["fresh"]
    assert m["large_model_requests_total"] == 1 and f["large_model_requests_total"] == 2
    assert m["routes"] == {"new_family": 1, "reuse": 1} and f["routes"] == {"new_family": 2}
    assert s["first_of_family"]["memory"]["runs"] == 1 and s["repeats_of_family"]["memory"]["runs_without_model_request"] == 1
    pos2 = s["positions"][1]["arms"]
    assert pos2["memory"][0]["snapshot_id"] != "v0" and pos2["fresh"][0]["snapshot_id"] == "v0"
    assert s["growth"][0]["experiences_end"] > s["growth"][0]["experiences_start"]
    assert s["series"]["memory"]["1"]["large_model_requests"] == [1, 1]
    assert memory.active_snapshot() == before
    assert len(evolution_note(cid)["lines"]) == 3
