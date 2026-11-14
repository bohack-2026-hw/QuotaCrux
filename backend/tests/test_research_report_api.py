"""Final-state reporting and portable research artifact API contracts."""
import json
import time
import uuid

from fastapi.testclient import TestClient
import pytest

from quotacrux import api, config, db, evaluator, report, research_views
from quotacrux.benchmarks import native


PRICE = {"model": "Qwen3.8-27B", "currency": "CNY", "unit": "per_1m_tokens",
         "input_per_1m": 3, "output_per_1m": 12, "source": "https://example.test/pricing",
         "retrieved_at": "2026-11-14T08:00:00+00:00"}


def stored_run(*, metric="speedup", status="completed", enabled=True, final=None, event=None):
    task = native.package("ale-bench", "fixture", "smoke", {"revision": "report-fixture"},
                          "Print a feasible output", "print(0)\n", [{"id": "dev", "input": "1"}],
                          [{"id": "final", "input": "2"}],
                          objective={"metric": metric, "direction": "maximize"}, settings={})
    run_id = "report-" + uuid.uuid4().hex
    cfg = {"research_protocol": {"mode": "no_feedback", "final_evaluation": enabled, "fixed_model": "small"},
           "limits": config.RunLimits().to_dict(), "measure": config.MeasureConfig().to_dict()}
    db.insert("runs", {"run_id": run_id, "task_id": task.task_id, "mode": "eval", "snapshot_id": "v0",
                       "config_json": db.dumps(cfg), "config_fingerprint": "fixture", "status": status,
                       "best_candidate_id": "c0", "stop_reason": "agent_finished", "started_at": db.now(),
                       "loop_ended_at": db.now(), "ended_at": None if status == "running" else db.now()})
    db.insert("candidates", {"run_id": run_id, "candidate_id": "c0", "seq": 0, "origin": "initial",
                             "code_path": str(task.dir / "initial.py"),
                             "code_sha256": task.manifest["files"]["initial"]["sha256"], "created_at": db.now()})
    if final:
        ev_status, correct = final
        detail = {"case_count": 1, "passed_cases": int(correct)}
        if metric == "score":
            detail["objective"] = {"metric": "score", "direction": "maximize", "value": 5, "baseline": 5}
        ev = evaluator.Evaluation(uuid.uuid4().hex, task.task_id, "final", ev_status, True,
                                  correct, correct, False, False, None, None, None, detail=detail)
        native.persist(task, ev, task.initial_code.encode(), db.now(), time.perf_counter(), run_id, "c0")
        db.update("runs", "run_id", run_id, {"final_evaluation_id": ev.evaluation_id})
    if event:
        db.add_event(run_id, event, {"error": "checker exploded"} if event == "final_eval_error" else {})
    return run_id, task.task_id


@pytest.mark.parametrize("status,enabled,final,event,expected", [
    ("completed", False, None, None, "disabled"),
    ("running", True, None, None, "pending"),
    ("completed", True, ("passed", True), None, "completed"),
    ("completed", True, ("timeout", False), None, "failed"),
    ("completed", True, ("unstable", True), None, "failed"),
    ("completed", True, None, "final_eval_error", "failed"),
    ("interrupted", True, None, "final_eval_started", "failed"),
    ("stopped", True, None, "final_eval_skipped", "not_run"),
])
def test_final_states_are_explicit_in_report_and_run_list(status, enabled, final, event, expected):
    run_id, task_id = stored_run(status=status, enabled=enabled, final=final, event=event)
    rep = report.build(run_id)
    assert rep["outcome"]["final_status"] == expected
    assert rep["research_mode"] == "no_feedback" and rep["dev_only"] is not enabled
    if expected == "failed":
        assert rep["outcome"]["valid_artifact"] is False
        assert rep["outcome"]["run_completed"] is False
        assert rep["outcome"]["final_error"]
        assert "失败" in rep["outcome"]["summary"] or "异常" in rep["outcome"]["summary"]
    with TestClient(api.app) as client:
        rows = client.get("/api/runs", params={"task_id": task_id}).json()
        row = next(x for x in rows if x["run_id"] == run_id)
        assert row["research_mode"] == "no_feedback" and row["final_status"] == expected
        assert row["dev_only"] is not enabled
        assert not any(key.startswith("_") for key in row)


def test_c0_is_normalized_for_speedup_but_native_score_stays_measured():
    run_id, _ = stored_run(final=("passed", True))
    rep = report.build(run_id)
    final = rep["final_evaluation"]
    assert final["speedup"] == rep["outcome"]["final_speedup"] == 1.0
    assert final["normalized"] is True and final["measured"] is False
    assert final["candidate_median_s"] is None and final["baseline_median_s"] is None
    score_id, _ = stored_run(metric="score", final=("passed", True))
    score = report.build(score_id)["final_evaluation"]
    assert score["speedup"] is None and score["objective"]["value"] == 5
    assert score["normalized"] is False and score["measured"] is True


def test_frozen_cost_distinguishes_currency_unknown_tokens_and_zero_requests():
    cost = research_views.estimate_cost({"requests": 1, "input_tokens": 1000, "output_tokens": 100}, PRICE)
    assert cost["amount"] == pytest.approx(0.0042)
    assert cost["currency"] == "CNY" and cost["status"] == "estimated" and cost["price_snapshot"] == PRICE
    incomplete = research_views.estimate_cost({"requests": 2, "input_tokens": 1000,
                                              "input_tokens_unknown_calls": 1, "output_tokens": 100}, PRICE)
    assert incomplete["amount"] is None and incomplete["status"] == "unknown"
    assert research_views.estimate_cost({"requests": 1}, None)["amount"] is None
    assert research_views.estimate_cost({"requests": 0}, None)["status"] == "no_model_calls"
    assert research_views.estimate_cost({"requests": 0}, PRICE)["amount"] == 0
    for invalid in ({**PRICE, "input_per_1m": float("nan")}, {**PRICE, "currency": "¥"},
                    {**PRICE, "retrieved_at": "2026-11-14"}, {**PRICE, "unit": "per_token"}):
        with pytest.raises(ValueError):
            research_views.validate_pricing(invalid)


@pytest.mark.parametrize("fair", [True, False, None])
def test_research_api_reads_portable_json_and_keeps_fair_tristate(tmp_path, monkeypatch, fair):
    monkeypatch.setattr(config, "VAR_DIR", tmp_path)
    root = tmp_path / "comparisons"
    root.mkdir()
    data = {"comparison_id": "research-portable", "protocol": "within-task-feedback-v2", "status": "completed",
            "fair": fair, "final_evaluation": True, "price_snapshot": PRICE,
            "runs": [{"task_id": "task-on-another-host", "task": {"task_id": "task-on-another-host",
                       "family": "algotune", "objective": {"metric": "speedup", "direction": "maximize"}},
                      "repeat": 1, "mode": "no_feedback", "status": "completed", "best_dev": {"status": "passed"},
                      "final_evaluation": {"status": "passed", "correct": True, "speedup": 1.0,
                                           "normalized": True, "measured": False},
                      "usage": {"requests": 1, "input_tokens": 1000, "output_tokens": 100},
                      "progress": [{"elapsed_s": 1, "value": 1}], "report_path": "/missing-worker/report.json"}]}
    (root / "research-portable.json").write_text(json.dumps(data))
    with TestClient(api.app) as client:
        response = client.get("/api/research-comparisons/research-portable")
        assert response.status_code == 200
        detail = response.json()
        assert detail["fair"] is fair and detail["api_contract"] == "research-comparison-v1"
        assert detail["runs"][0]["progress"] == data["runs"][0]["progress"]
        assert detail["runs"][0]["final_status"] == "completed" and detail["runs"][0]["dev_status"] == "passed"
        listing = client.get("/api/research-comparisons").json()[0]
        assert listing["fair"] is fair and listing["runs_total"] == listing["runs_finished"] == 1
        assert listing["final_status_counts"] == {"completed": 1}
        assert listing["cost"]["currency"] == "CNY" and listing["cost"]["amount"] == pytest.approx(0.0042)
        assert client.get("/api/research-comparisons/research-missing").status_code == 404


def test_portable_view_does_not_hide_failed_or_missing_final():
    base = {"comparison_id": "research-incomplete", "status": "completed", "fair": None, "final_evaluation": True}
    failed = {"task_id": "task", "mode": "feedback", "status": "completed", "outcome": {"final_error": "checker error"}}
    result = research_views.comparison_view({**base, "runs": [failed]})
    assert result["status"] == result["runs"][0]["status"] == "failed"
    missing = research_views.comparison_view({**base, "runs": [{"task_id": "task", "mode": "independent", "status": "completed"}]})
    assert missing["status"] == "interrupted" and missing["runs"][0]["final_status"] == "not_run"
    disabled = research_views.comparison_view({**base, "final_evaluation": False, "runs": [failed]})
    assert disabled["runs"][0]["final_status"] == "disabled"


def test_research_api_rejects_bad_identity_and_reports_corrupt_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VAR_DIR", tmp_path)
    root = tmp_path / "comparisons"
    root.mkdir()
    outside = tmp_path / "secret.json"
    outside.write_text('{"secret":"not exposed"}')
    (root / "research-symlink.json").symlink_to(outside)
    with pytest.raises(KeyError):
        research_views.load("research-symlink")
    (root / "research-symlink.json").unlink()
    (root / "research-corrupt.json").write_text("{")
    with TestClient(api.app) as client:
        assert client.get("/api/research-comparisons/research-corrupt").status_code == 500
        assert client.get("/api/research-comparisons").status_code == 500
