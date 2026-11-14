"""Evaluator behaviour on a sorted workload: contract cases catch distribution-specific shortcuts."""

from pathlib import Path

import pytest

from conftest import requires_docker

CANDS = Path(__file__).parent / "fixtures" / "cands"


@pytest.fixture(scope="module")
def sorted_task():
    from quotacrux import taskpkg

    return taskpkg.build_task("groupagg", {"task_id": "t-sorted", "split": "smoke",
                                           "params": {"rows": 200000, "keys": 2000, "order": "sorted"},
                                           "dev_seed": 21, "final_seed": 22})


def evaluate(task, name: str, timing: bool = False):
    from quotacrux import config, evaluator

    return evaluator.evaluate(task, (CANDS / name).read_bytes(), "dev", config.MeasureConfig(), config.RunLimits(),
                              measure_timing=timing)


@requires_docker
def test_unchecked_groupby_passes_dev_but_violates_contract(sorted_task):
    ev = evaluate(sorted_task, "groupby_unsorted_bug.py")
    assert ev.executed and ev.status == "contract_violation"
    assert ev.detail["failure"]["contract_case"] in ("interleaved_repeats", "ascii_order", "nearly_sorted_trap")


@requires_docker
def test_checked_groupby_passes_contract_and_is_timed(sorted_task):
    ev = evaluate(sorted_task, "groupby_checked.py", timing=True)
    assert ev.status == "passed" and ev.correct and ev.speedup is not None


@requires_docker
def test_initial_program_passes_contract(sorted_task):
    assert evaluate(sorted_task, "same_as_initial.py").status == "passed"
