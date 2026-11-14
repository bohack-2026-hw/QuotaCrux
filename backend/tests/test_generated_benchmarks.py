"""The benchmark boundary preserves generated families and task-specific memory routing."""
import json

import pytest

from quotacrux import config, evaluator, families, memory, taskpkg
from quotacrux.sandbox import executor


PARAMS = {
    "groupagg": {"rows": 40, "keys": 5},
    "logstats": {"rows": 40, "endpoints": 5, "hours": 2},
    "intervals": {"rows": 40},
}


def test_groupagg_preserves_existing_package_identity(tmp_path):
    task = taskpkg.build_task("groupagg", {"task_id": "generated-compat", "split": "smoke",
        "params": PARAMS["groupagg"], "dev_seed": 31, "final_seed": 32}, out_root=tmp_path)
    # The interpreter version is recorded but varies across test hosts.
    portable = {k: v for k, v in task.manifest.items() if k != "generator_python"}
    assert taskpkg.sha256_bytes(json.dumps(portable, sort_keys=True).encode()) == \
        "138021000cba67faedeba646fbc3a7ba61e973e1ffc3a2ac825a3a485481dcef"


@pytest.mark.parametrize("family", list(PARAMS))
def test_generated_adapter_dispatches_public_cases_and_judging(tmp_path, monkeypatch, family):
    task = taskpkg.build_task("groupagg", {"task_id": f"generated-dispatch-{family}", "family": family,
        "split": "T", "params": PARAMS[family], "dev_seed": 41, "final_seed": 42}, out_root=tmp_path)
    fam = families.get(family)
    assert task.family == family and task.fam is fam
    assert task.adapter.buckets(task.dev_profile) == fam.buckets(task.dev_profile)
    assert task.presentation["title"] == fam.TITLE_ZH
    assert {c.name for c in task.adapter.public_cases(task)} == set(fam.CONTRACT_CASES)
    seen = []

    def sample(code, data, *args, **kwargs):
        seen.append(data)
        return executor.SampleResult("ok", 0.01, 0.001, 0, fam.reference_output(data), "")

    monkeypatch.setattr(executor, "run_sample", sample)
    result = evaluator.evaluate(task, b"fixture", "dev", config.MeasureConfig(), config.RunLimits(), measure_timing=False)
    assert result.status == "passed" and result.correct
    assert len(seen) == 1 + len(fam.CONTRACT_CASES)
    assert seen[0] == task.dataset("dev")[0].read_bytes()


def test_mixed_spec_accepts_sealed_and_tuning_splits(tmp_path):
    spec = tmp_path / "spec-mixed.json"
    spec.write_text(json.dumps({"tasks": [
        {"task_id": f"generated-mixed-{family}", "family": family, "split": split,
         "params": PARAMS[family], "dev_seed": 51, "final_seed": 52}
        for family, split in (("logstats", "S"), ("intervals", "T"))]}))
    tasks = taskpkg.build_spec(spec)
    assert [(task.family, task.split) for task in tasks] == [("logstats", "S"), ("intervals", "T")]
    assert all("tasks build" in taskpkg.rebuild_command(task.task_id) for task in tasks)


def test_router_summary_counts_family_before_semantic_filter(monkeypatch):
    records = {
        "same-family": {"conditions": {"family": "algotune", "buckets": {"problem": "other-task"}}},
        "other-family": {"conditions": {"family": "logstats", "buckets": {}}},
    }
    monkeypatch.setattr(memory, "snapshot_experience_ids", lambda _: list(records))
    monkeypatch.setattr(memory, "experience", records.__getitem__)
    selected, summary = memory.retrieve("fixture", "algotune", {"memory_key": "current-task"})
    assert selected == [] and summary["matched_by_outcome"] == {}
    assert summary["family"] == "algotune" and summary["family_records"] == 1
    assert summary["min_matches"] == summary["feature_count"] == 1
