"""Portable routing evidence; all executions use scripted providers and fake judges."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from routeevo import routing_ablation as ablation
from test_routing import harness


@pytest.fixture
def result(harness):
    harness.action_choices *= 2
    return ablation.execute([harness.task.task_id], "v0")


def test_portable_fairness_is_per_task_and_retains_failures(result):
    other = deepcopy(result["runs"])
    for row in other:
        row["seq"] += 4
        row["task_id"] = row["task"]["task_id"] = row["execution"]["task_id"] = "another-task"
        row["comparison_config"]["task_manifest_sha256"] = "another-manifest"
        row["comparison_config"]["environment"] = {"image_id": "another-host"}
        row["comparison_config"]["config"]["sandbox_image_id"] = "another-host"
    result["runs"] += other
    result["plan"] += [{k: row[k] for k in ("seq", "task_id", "repeat", "variant", "routing")} for row in other]
    result["plan_sha256"] = ablation._plan_hash(result["plan"])
    assert ablation.summarize(result)["fair"] is True
    assert len(result["summary"]["tasks"]) == 2
    assert len(result["summary"]["pairs"]) == 12
    result["runs"][-1].update(status="failed", final_status="failed", final_evaluation=None)
    ablation.summarize(result)
    assert result["fair"] is True  # protocol equality and final success are separate facts
    assert not result["fairness"]["all_final_evaluations_completed"]
    group = result["summary"]["tasks"][1]["variants"][3]
    assert group["planned"] == group["failed"] == 1
    assert group["final_values"] == [None]
    assert result["summary"]["interactions"][1]["status"] == "missing_or_failed"
    result["runs"][-1]["comparison_config"]["environment"]["image_id"] = "drifted"
    assert ablation.summarize(result)["fair"] is False


def test_plan_and_actual_routing_must_match_even_after_export(result):
    changed = deepcopy(result)
    changed["runs"][0]["execution"]["routing"]["model"] = "decisions"
    assert ablation.summarize(changed)["fair"] is False
    result["runs"].pop()
    assert ablation.summarize(result)["fair"] is False
    assert result["summary"]["planned"] == 4


def test_interruption_preserves_unrun_slots_and_releases_lock(harness, monkeypatch):
    monkeypatch.setattr(ablation.Runner, "execute", lambda self: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        ablation.execute([harness.task.task_id], "v0")
    paths = sorted((ablation.config.VAR_DIR / "comparisons").glob("research-routing-*.json"), key=lambda p: p.stat().st_mtime_ns)
    out = json.loads(paths[-1].read_text())
    assert out["status"] == "failed"
    assert [r["status"] for r in out["runs"]] == ["interrupted", "not_run", "not_run", "not_run"]
    assert out["summary"]["not_run"] == 3 and out["fair"] is None
    lock = ablation.compare._try_lock()
    assert lock is not None
    lock.close()


def price(model, currency, input_rate, output_rate):
    return {"model": model, "currency": currency, "input_per_1m": input_rate, "output_per_1m": output_rate,
            "unit": "per_1m_tokens", "source": "fixture", "retrieved_at": "2026-11-14T00:00:00Z"}


def test_costs_keep_currencies_purposes_and_partial_usage():
    pricing = {"small": price("qwen", "CNY", 1, 2), "large": price("gpt", "USD", 3, 6),
               "decisions": price("decision", "USD", 0.1, 0)}
    ledgers = {
        "small:chat_compat:qwen": {"requests": 1, "input_tokens": 1000, "output_tokens": 100},
        "large:openai_responses:gpt": {"requests": 2, "input_tokens": 2000, "output_tokens": 100,
                                      "input_tokens_unknown_calls": 1, "output_tokens_unknown_calls": 1,
                                      "errors": {"timeout": 1}},
        "router_model:openai_decisions:decision": {"requests": 1, "input_tokens": 500, "output_tokens": 0},
    }
    cost = ablation.costs(ledgers, pricing)
    assert cost["by_currency"]["CNY"]["amount"] == pytest.approx(0.0012)
    assert cost["by_currency"]["USD"]["amount"] is None
    assert cost["by_currency"]["USD"]["known_amount"] == pytest.approx(0.00665)
    assert cost["by_currency"]["USD"]["status"] == "partial"
    assert cost["by_model"]["large:openai_responses:gpt"]["usage"]["errors"] == {"timeout": 1}
    assert cost["by_model"]["router_model:openai_decisions:decision"]["purpose"] == "routing"
    unknown = ablation.costs(ledgers, {})
    assert unknown["by_currency"] == {} and unknown["unpriced_model_ledgers"] == 3
    assert all(row["amount"] is None for row in unknown["by_model"].values())
    assert ablation._sum_usage([ledgers["large:openai_responses:gpt"]])["input_tokens_unknown_calls"] == 1


@pytest.mark.parametrize("change", [lambda rows: rows[0].update(status="completed"),
    lambda rows: rows[0].update(routing={"action": "decisions", "model": "rule"}),
    lambda rows: rows[1].update(seq=rows[0]["seq"])])
def test_invalid_plan_rejected_before_a_runner(harness, monkeypatch, change):
    rows = ablation.plan([harness.task.task_id], 1)
    change(rows)
    monkeypatch.setattr(ablation, "Runner", lambda *a: pytest.fail("invalid plan must not construct a runner"))
    with pytest.raises(ValueError):
        ablation.execute([harness.task.task_id], "v0", plan=rows)
