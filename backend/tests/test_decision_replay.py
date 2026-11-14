import copy
import importlib.util
import json
from pathlib import Path
import shutil

import httpx
import pytest

from quotacrux.llm import openai_decisions as decisions

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("decision_replay", ROOT / "backend/scripts/decision_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def response_data():
    return {"model": decisions.MODEL, "answers": [{"type": "choice", "name": "next_model", "choice": "large",
            "confidence": 0.8, "probabilities": [{"value": "small", "probability": 0.2}, {"value": "large", "probability": 0.8}]}],
            "usage": {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 100},
                      "output_tokens": 0}}


def mock_response(monkeypatch, data, status=200):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(status, json=data, headers={"x-request-id": "req-test"})
    monkeypatch.setattr(decisions.httpx, "post", post)
    return calls


def test_decisions_transport_and_cache_accounting(monkeypatch):
    calls = mock_response(monkeypatch, response_data())
    result = decisions.decide({"observation": "test"}, [replay.ROUTE_QUESTION])
    assert result.ok and json.loads(result.text)[0]["choice"] == "large"
    assert calls[0][0] == "https://api.openai.com/v1/decisions"
    assert result.request_body["prompt_cache_options"] == {"mode": "explicit"}
    assert "Authorization" not in json.dumps(result.request_body)
    assert decisions.estimate_decision_cost(result) == pytest.approx(0.0000845)


@pytest.mark.parametrize("failure", ["missing", "wrong_name", "unknown_choice", "bad_probability", "bad_distribution", "refusal"])
def test_unusable_answers_are_explicit_failures(monkeypatch, failure):
    data = response_data()
    answer = data["answers"][0]
    if failure == "missing":
        data["answers"] = []
    elif failure == "wrong_name":
        answer["name"] = "unrelated"
    elif failure == "unknown_choice":
        answer["choice"] = "finish"
    elif failure == "bad_probability":
        answer["confidence"] = 1.1
    elif failure == "bad_distribution":
        answer["probabilities"][0]["value"] = 1
    else:
        answer["type"] = "refusal"
    mock_response(monkeypatch, data)
    result = decisions.decide({}, [replay.ROUTE_QUESTION])
    assert not result.ok
    assert result.error_kind == ("refusal" if failure == "refusal" else "bad_response")
    assert result.usage.input_tokens == 1000


def test_timeout_has_unknown_cost_and_no_retry(monkeypatch):
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(decisions.httpx, "post", timeout)
    result = decisions.decide({}, [replay.ROUTE_QUESTION])
    assert result.error_kind == "timeout" and len(calls) == 1
    assert decisions.estimate_decision_cost(result) is None


def test_missing_key_does_not_send(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = mock_response(monkeypatch, response_data())
    result = decisions.decide({}, [replay.ROUTE_QUESTION])
    assert result.error_kind == "config" and calls == []
    assert decisions.estimate_decision_cost(result) == 0


@pytest.mark.parametrize("field", ["input_tokens_details", "output_tokens_details"])
def test_invalid_usage_details_are_a_recorded_response_failure(monkeypatch, field):
    data = response_data()
    data["usage"][field] = "invalid"
    mock_response(monkeypatch, data)
    result = decisions.decide({}, [replay.ROUTE_QUESTION])
    assert not result.ok and result.error_kind == "bad_response"


def test_heldout_bundle_is_rejected_before_loading_inputs(tmp_path):
    replay.write_json(tmp_path / "report.json", {"task": {"split": "D"}, "scripted_model": False})
    with pytest.raises(ValueError, match="A/B"):
        replay.prepare_bundle(tmp_path)


def test_future_results_do_not_enter_evidence(tmp_path):
    source = ROOT / "docs/research/run-20261113T161733-7c5a"
    shutil.copytree(source, tmp_path / "bundle")
    bundle = tmp_path / "bundle"
    before = replay.prepare_bundle(bundle)
    report = json.loads((bundle / "report.json").read_text())
    report["final_evaluation"] = {"canary": "SECRET_FINAL_SENTINEL"}
    report["task"]["final_params"] = {"canary": "SECRET_FINAL_SENTINEL"}
    for step in report["steps"]:
        if step["action"] == "run_validation":
            step["result"]["canary"] = "FUTURE_EVALUATION_SENTINEL"
    replay.write_json(bundle / "report.json", report)
    after = replay.prepare_bundle(bundle)
    assert [c["evidence"] for c in before] == [c["evidence"] for c in after]
    assert "SENTINEL" not in json.dumps([c["evidence"] for c in after])


def test_reuse_prefix_excludes_current_validation_results():
    cases = replay.prepare_bundle(ROOT / "docs/research/run-20261113T212515-d6bd")
    reuse = [c for c in cases if c["kind"] == "candidate" and c["source"]["origin"] == "reuse_candidate"]
    assert len(reuse) == 3
    for case in reuse:
        evidence = json.dumps(case["evidence"])
        assert "latest_evaluation" not in evidence
        assert case["reference"]["evaluation_id"] not in evidence
        assert "## Candidates" not in evidence


def test_compact_view_preserves_code_target_and_labels():
    cases = replay.prepare_bundle(ROOT / "docs/research/run-20261113T212515-d6bd")
    originals = [c for c in cases if c["kind"] == "candidate"]
    compact = replay.compact_candidates(cases)
    assert len(compact) == len(originals) == 6
    for original, reduced in zip(originals, compact):
        assert original["reference"] == reduced["reference"]
        assert original["questions"] == reduced["questions"]
        for key in ("target_speedup", "proposed_candidate"):
            assert original["evidence"][key] == reduced["evidence"][key]
        assert set(reduced["evidence"]) == {"task_and_profile", "initial_program", "proposed_candidate", "target_speedup"}
        assert "latest_evaluation" not in json.dumps(reduced["evidence"])
        assert "def main():" in reduced["evidence"]["initial_program"]


def test_labels_are_not_transmitted_and_failed_attempt_is_saved(monkeypatch, tmp_path):
    calls = mock_response(monkeypatch, {"error": {"message": "rate limited"}}, status=429)
    case = {"id": "sample", "kind": "route", "source": {}, "evidence": {"current": 1},
            "questions": [replay.ROUTE_QUESTION], "reference": {"SECRET_LABEL": True}}
    with pytest.raises(RuntimeError, match="rate_limit"):
        replay.run([case, copy.deepcopy(case)], tmp_path / "output", None, 1)
    assert len(calls) == 1 and "SECRET_LABEL" not in json.dumps(calls[0][1]["json"])
    summary = json.loads((tmp_path / "output/summary.json").read_text())
    assert summary["requests"] == 1 and summary["errors"] == 1 and summary["cost_unknown_requests"] == 1
