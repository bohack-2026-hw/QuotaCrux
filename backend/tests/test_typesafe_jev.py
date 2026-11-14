import json

import httpx
import pytest

from quotacrux.agent import routing
from quotacrux.config import RoutingConfig
from quotacrux.llm import typesafe_jev as jev


def response_data():
    return {"model": jev.MODEL, "answers": {"model": {
        "type": "choice", "choice": "large", "confidence": 0.8,
        "probabilities": {"small": 0.2, "large": 0.8}}},
        "usage": {"input_tokens": 1000, "output_tokens": 34}}


def mock_response(monkeypatch, data, status=200):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(status, json=data, headers={"x-request-id": "req-jev"})

    monkeypatch.setattr(jev.httpx, "post", post)
    return calls


def test_choice_wire_contract_normalization_and_accounting(monkeypatch):
    raw = response_data()
    calls = mock_response(monkeypatch, raw)
    result = jev.decide({"candidate_misses": 2}, [routing.MODEL_QUESTION], 5, model="jev-latest")
    assert result.ok and result.request_id == "req-jev"
    url, args = calls[0]
    assert url == "https://api.typesafe.ai/v1/systemone"
    assert args["headers"]["Authorization"] == "Bearer test-no-network"
    assert args["timeout"].read == args["timeout"].connect == 5
    body = args["json"]
    assert body["model"] == "jev-latest" and body["state"] == {"candidate_misses": 2}
    assert body["questions"]["model"]["criteria"] == {c["value"]: c["description"] for c in routing.MODEL_QUESTION["choices"]}
    assert routing.MODEL_INSTRUCTIONS in body["questions"]["model"]["instructions"]
    answer = json.loads(result.text)[0]
    assert answer["name"] == "model" and answer["choice"] == "large"
    assert answer["probabilities"] == [{"value": "small", "probability": 0.2}, {"value": "large", "probability": 0.8}]
    assert result.response_body == raw and "test-no-network" not in json.dumps(result.__dict__, default=str)
    assert result.usage.input_tokens == 1000 and result.usage.output_tokens == 34
    assert result.usage.cached_input_tokens is None
    assert jev.estimate_decision_cost(result) == pytest.approx(0.000042)


@pytest.mark.parametrize("failure", ["missing", "wrong_type", "unknown_choice", "missing_option", "extra_option",
    "nan", "boolean", "sum", "not_maximum", "confidence", "invalid_usage", "missing_usage", "missing_model"])
def test_bad_responses_fail_explicitly(monkeypatch, failure):
    data = response_data()
    answer = data["answers"]["model"]
    if failure == "missing":
        data["answers"] = {}
    elif failure == "wrong_type":
        answer["type"] = "noul"
    elif failure == "unknown_choice":
        answer["choice"] = "finish"
    elif failure == "missing_option":
        answer["probabilities"] = {"large": 1.0}
    elif failure == "extra_option":
        answer["probabilities"]["finish"] = 0.0
    elif failure in ("nan", "boolean", "sum"):
        answer["probabilities"]["small"] = {"nan": float("nan"), "boolean": True, "sum": 0.5}[failure]
    elif failure == "not_maximum":
        answer["choice"] = "small"
    elif failure == "confidence":
        answer["confidence"] = 1.1
    elif failure == "invalid_usage":
        data["usage"]["input_tokens"] = -1
    elif failure == "missing_usage":
        del data["usage"]
    else:
        del data["model"]
    # A raw JSON response also exercises nonstandard NaN values received from an upstream.
    monkeypatch.setattr(jev.httpx, "post", lambda *a, **kw: httpx.Response(200, content=json.dumps(data)))
    result = jev.decide({}, [routing.MODEL_QUESTION])
    assert not result.ok and result.error_kind == "bad_response"
    if failure not in ("invalid_usage", "missing_usage"):
        assert result.usage.input_tokens == 1000


@pytest.mark.parametrize("status,kind", [(401, "http_4xx"), (429, "rate_limit"), (503, "http_5xx")])
def test_http_failures_do_not_retry(monkeypatch, status, kind):
    calls = mock_response(monkeypatch, {"detail": "upstream failure"}, status)
    result = jev.decide({}, [routing.MODEL_QUESTION])
    assert result.error_kind == kind and len(calls) == 1
    assert result.usage.input_tokens is None and jev.estimate_decision_cost(result) is None


def test_timeout_and_missing_key_do_not_retry_or_invent_usage(monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(jev.httpx, "post", timeout)
    result = jev.decide({}, [routing.MODEL_QUESTION])
    assert result.error_kind == "timeout" and len(calls) == 1
    assert result.usage.input_tokens is None and jev.estimate_decision_cost(result) is None
    monkeypatch.delenv("TYPESAFE_API_KEY")
    result = jev.decide({}, [routing.MODEL_QUESTION])
    assert result.error_kind == "config" and len(calls) == 1
    assert jev.estimate_decision_cost(result) == 0


def test_model_selection_is_frozen_in_router_and_manifest(monkeypatch):
    monkeypatch.setenv("TYPESAFE_MODEL", "jev-latest")
    config = RoutingConfig("jev", "jev")
    action, model = routing.make_routers(config, {}, {})
    manifest = routing.manifest(config)
    assert manifest["jev_model"] == "jev-latest" and manifest["jev_endpoint"] == jev.ENDPOINT
    monkeypatch.setenv("TYPESAFE_MODEL", "jev-preview")
    calls = mock_response(monkeypatch, response_data())
    state = routing.RoutingState("system", "state", "small", 0, 0, 5, 2, (), 2, {})
    assert model.request(state, 5).ok
    assert calls[0][1]["json"]["model"] == action.config_for("small").model == "jev-latest"
    assert model.config_for("large") is None
    result = jev.decide({}, [routing.MODEL_QUESTION])
    result.model_returned = "jev-future"
    assert jev.estimate_decision_cost(result) is None
