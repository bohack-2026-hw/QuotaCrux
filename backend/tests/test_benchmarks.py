"""Adapter boundaries: immutable data, isolated judging and task-specific experience."""
import copy
import dataclasses
import json
import os
import uuid

import pytest

from conftest import requires_docker
from routeevo import config, evaluator, memory, taskpkg
from routeevo.benchmarks import Case, effibench
from routeevo.sandbox import executor


def record(interface="io"):
    return {
        "id": "double", "source": "fixture", "type": interface, "title": "Double an integer",
        "description_md": "Read an integer and output twice its value.",
        "solutions": {"python3": {"code": "print(int(input()) * 2)" if interface == "io" else
                                  "class Solution:\n    def double(self, value: int) -> int:\n        return value * 2\n"}},
        "test_runners": {"python3": "==Code Submission==\nprint(Solution().double(int(sys.stdin.read())))\n"},
        "evaluator": "def evaluate(actual, expected):\n    return int(actual) == int(expected)\n",
        "generated_tests": json.dumps([{"input": f"{n}\n", "output": f"{n * 2}\n"} for n in (1, 2, 3, 4, 1)]),
    }


def build(rec=None, **kwargs):
    return effibench.build_record(rec or record(), split="smoke", dev_cases=kwargs.pop("dev_cases", 2),
                                 provenance={"revision": "fixture-v1"},
                                 task_id=kwargs.pop("task_id", "test-ebx-" + uuid.uuid4().hex[:8]), **kwargs)


def test_package_is_deterministic_and_final_is_private():
    task = build()
    assert task.manifest == build(task_id=task.task_id).manifest
    assert task.manifest["selection"]["raw_cases"] == 5
    assert task.manifest["selection"]["unique_cases"] == 4
    dev, final = (task.adapter.cases(task, ds) for ds in ("dev", "final"))
    assert {c.input for c in dev}.isdisjoint({c.input for c in final})
    assert all(e["input"].encode() in {c.input for c in dev} for e in task.examples)
    assert "checker" not in task.manifest["agent_visible"]
    changed = record()
    changed["solutions"]["python3"]["code"] = "print(int(input()) * 3)"
    with pytest.raises(RuntimeError, match="immutable"):
        build(changed, task_id=task.task_id)
    assert taskpkg.load(task.task_id).manifest == task.manifest
    (task.dir / "checker.py").write_text("modified")
    with pytest.raises(RuntimeError, match="modified"):
        taskpkg.load(task.task_id)


@pytest.mark.parametrize("change", ["conflicting_duplicate", "empty_output", "missing_runner", "third_party"])
def test_rejects_unsupported_records(change):
    rec = record("functional")
    if change == "conflicting_duplicate":
        tests = json.loads(rec["generated_tests"])
        tests[-1]["output"] = "99"
        rec["generated_tests"] = json.dumps(tests)
    elif change == "empty_output":
        rec["generated_tests"] = '[{"input":"1","output":null}]'
    elif change == "missing_runner":
        rec["test_runners"] = None
    else:
        rec["solutions"]["python3"]["code"] = "x = SortedList()"
    with pytest.raises(ValueError):
        build(rec)


def test_rejects_wrong_shard_before_loading(tmp_path):
    pytest.importorskip("pyarrow")
    path = tmp_path / "bad.parquet"
    path.write_bytes(b"not parquet")
    with pytest.raises(ValueError, match="pinned"):
        effibench.import_problem("leetcode/3188", split="smoke", parquet=path)


@pytest.mark.parametrize("interface", ["io", "functional"])
def test_parquet_nested_columns_round_trip(tmp_path, monkeypatch, interface):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    rec = {**record(interface), "time_limit_nanos": 10**9, "memory_limit_bytes": 1024**3}
    path = tmp_path / "source.parquet"
    pq.write_table(pa.Table.from_pylist([rec]), path)
    monkeypatch.setattr(effibench, "CATALOG", {
        "dataset": "fixture", "problems": [{"key": "fixture/double", "shard": 0}],
        "shards": [{"file": "source.parquet", "bytes": path.stat().st_size, "sha256": taskpkg.sha256_file(path)}],
    })
    task = effibench.import_problem("fixture/double", split="smoke", dev_cases=2, parquet=path,
                                    task_id="parquet-" + uuid.uuid4().hex[:8])
    assert rec["solutions"]["python3"]["code"] in task.initial_code
    assert task.manifest["selection"]["unique_cases"] == 4
    assert len(task.adapter.cases(task, "final")) == 2


def test_memory_key_isolated_by_problem_and_dev_partition(monkeypatch):
    task = build()
    changed = record()
    changed["id"] = "another-problem"
    other, other_partition = build(changed), build(dev_cases=1)
    assert len({t.dev_profile["memory_key"] for t in (task, other, other_partition)}) == 3
    exp = {
        "experience_id": "same", "outcome": "success", "created_at": "2026-01-01",
        "conditions": {"family": "effibench-x", "task_id": task.task_id,
                       "buckets": effibench.buckets(task.dev_profile), "profile": task.dev_profile},
        "action": {"code": task.initial_code, "parent_candidate_id": "c0", "code_features": {}, "diff_vs_initial": ""},
        "result": {"speedup": 2}, "hypothesis": None,
        "resources": {"model_role": "small", "output_tokens": 2, "latency_s": 1},
        "source": {"run_id": "r", "step_seq": 1, "candidate_id": "c1"},
    }
    wrong = copy.deepcopy(exp)
    wrong["experience_id"] = "other"
    wrong["conditions"]["buckets"] = effibench.buckets(other.dev_profile)
    monkeypatch.setattr(memory, "snapshot_experience_ids", lambda _: ["same", "other"])
    monkeypatch.setattr(memory, "experience", lambda k: {"same": exp, "other": wrong}[k])
    for method in (memory.retrieve, memory.reusable_programs):
        matches, _ = method("test", "effibench-x", task.dev_profile)
        assert [r["experience_id"] for r in matches] == ["same"]
        assert method("test", "effibench-x", other_partition.dev_profile)[0] == []


def test_suite_timing_sums_every_case(monkeypatch):
    task = build()
    def sample(code, data, timeout, measure, profile=False):
        n = int(data)
        return executor.SampleResult("ok", float(n * (2 if code == b"baseline" else 1)), 0.1, 0,
                                     str(n * 2).encode(), "")
    monkeypatch.setattr(executor, "run_sample", sample)
    monkeypatch.setattr(effibench, "check_outputs", lambda task, cases, outputs, *args:
                        {"format_ok": True, "correct": all(int(o) == int(c.expected) for c, o in zip(cases, outputs))})
    ev = evaluator.evaluate(task, b"candidate", "dev", config.MeasureConfig(repeats=2), config.RunLimits(), baseline_code=b"baseline")
    expected = sum(int(c.input) for c in task.adapter.cases(task, "dev"))
    assert ev.status == "passed" and ev.speedup == 2 and ev.improved
    assert ev.detail["timing"]["candidate_s"] == [expected] * 2
    assert ev.detail["timing"]["baseline_s"] == [2 * expected] * 2
    assert len(ev.detail["samples"]) == 12


def test_suite_bounds_total_candidate_output(monkeypatch):
    task = build()
    monkeypatch.setattr(executor, "run_sample", lambda *args, **kwargs:
                        executor.SampleResult("ok", 0.01, 0.01, 0, b"123456", ""))
    ev = evaluator.evaluate(task, b"candidate", "dev", config.MeasureConfig(max_output_bytes=10),
                            config.RunLimits(), measure_timing=False)
    assert ev.status == "output_limit" and len(ev.detail["samples"]) == 2


@requires_docker
@pytest.mark.parametrize("interface", ["io", "functional"])
def test_reference_passes_both_suites_and_wrong_candidate_fails(interface):
    task = build(record(interface))
    for dataset in ("dev", "final"):
        ev = evaluator.evaluate(task, task.initial_code.encode(), dataset, config.MeasureConfig(), config.RunLimits(), measure_timing=False)
        assert ev.status == "passed" and ev.correct
    ev = evaluator.evaluate(task, b"print(-1)", "dev", config.MeasureConfig(), config.RunLimits(), measure_timing=False)
    assert ev.status == "wrong_output" and ev.correct is False


@requires_docker
@pytest.mark.parametrize("checker", ["raise RuntimeError('judge failed')", "while True: pass"])
def test_checker_error_is_not_candidate_failure(checker):
    rec = record()
    rec["evaluator"] = "def evaluate(actual, expected):\n    " + checker + "\n"
    task = build(rec)
    limits = dataclasses.replace(config.RunLimits(), measurement_timeout_s=0.5)
    ev = evaluator.evaluate(task, task.initial_code.encode(), "dev", config.MeasureConfig(), limits, measure_timing=False)
    assert ev.status == "checker_error" and ev.correct is None
    assert ev.status in memory.NON_EVIDENCE_STATUSES


@requires_docker
def test_official_checker_argument_order_and_output_normalization():
    rec = record()
    rec["evaluator"] = "def evaluate(first, second):\n    return first == 'candidate' and second == 'reference'\n"
    task = build(rec)
    result = task.adapter.check_outputs(task, [Case("order", b"", b"reference\r\n")],
                                        [b"\x1b[31mcandidate\x1b[0m\r\n"], config.MeasureConfig(), config.RunLimits())
    assert result["correct"] is True


@requires_docker
def test_scripted_run_report_profile_and_export(tmp_path):
    from routeevo import api, cli, narrative
    from routeevo.agent.runner import RunOptions, Runner
    task = build(record("functional"))
    base = {"purpose": "验证适配流程", "expected_result": "正确性通过", "verification": "外部评测器"}
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"small": [
        {**base, "action": "get_evidence", "tool": "profile_candidate", "candidate_id": "c0"},
        {**base, "action": "propose_candidate", "code": task.initial_code, "parent_candidate_id": "c0"},
        {**base, "action": "finish", "finish_reason": "流程已验证"},
    ]}))
    get_affinity = getattr(os, "sched_getaffinity", None)
    cpuset = str(min(get_affinity(0))) if get_affinity is not None else "0"
    runner = Runner(RunOptions(task_id=task.task_id, snapshot_id="v0", script=script, router=False,
                               measure=config.MeasureConfig(repeats=1, cpuset_cpus=cpuset, function_warmups=3)))
    runner.create()
    rep = runner.execute()
    assert rep["outcome"]["final_correct"]
    assert rep["iterations"]["evidence_calls"] == 1
    assert rep["research"]["definition"]["workload"] == task.presentation["workload"]
    assert "分组聚合" not in rep["research"]["definition"]["question"]
    assert next(t for t in api.list_tasks() if t["task_id"] == task.task_id)["family"] == "effibench-x"
    out = tmp_path / "bundle"
    cli.export_bundle(rep["run_id"], out, narrative.run_markdown(rep["run_id"]))
    assert "import-effibench" in (out / "reproduce.sh").read_text()
    check_line = next(line for line in (out / "reproduce.sh").read_text().splitlines()
                      if line.startswith("uv run routeevo check"))
    assert f"--cpuset-cpus {cpuset}" in check_line and "--function-warmups 3" in check_line


@requires_docker
def test_candidate_checker_error_stops_without_upgrade_or_learning(tmp_path):
    from routeevo.agent.runner import RunOptions, Runner
    rec = record()
    rec["evaluator"] = "def evaluate(actual, expected):\n    if actual == 'bad': raise RuntimeError('checker error')\n    return int(actual) == int(expected)\n"
    task = build(rec)
    script = tmp_path / "bad-checker.json"
    script.write_text(json.dumps({"small": [{"action": "propose_candidate", "purpose": "触发校验器异常", "expected_result": "明确停止",
                                            "verification": "外部评测器", "code": "print('bad')", "parent_candidate_id": "c0"}]}))
    runner = Runner(RunOptions(task_id=task.task_id, mode="learn", snapshot_id="v0", script=script, router=False))
    runner.create()
    rep = runner.execute()
    assert rep["stop_reason"] == "environment_error"
    assert rep["iterations"]["model_requests"] == 1 and rep["iterations"]["upgrades"] == 0
    assert rep["experience"]["published_snapshot_id"] is None
    assert rep["final_evaluation"] is None
