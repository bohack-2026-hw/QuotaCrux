import json

import pytest

from routeevo.agent import actions
from routeevo.llm.base import Usage
from routeevo.llm.pricing import estimate_cost


def _action(**kw):
    base = {"action": "analyze", "purpose": "p", "expected_result": "e", "verification": "v", "analysis": "a"}
    base.update(kw)
    return base


def test_parse_plain_fenced_and_wrapped_json():
    raw = json.dumps(_action())
    assert actions.parse(raw).action == "analyze"
    assert actions.parse(f"```json\n{raw}\n```").analysis == "a"
    assert actions.parse(f"Here you go: {raw} done").purpose == "p"


@pytest.mark.parametrize("text,kind", [
    ("nope", "not_json"),
    (json.dumps(_action(action="hack")), "unknown_action"),
    (json.dumps(_action(purpose="")), "missing_field"),
    (json.dumps(_action(code=5)), "bad_field"),
])
def test_parse_rejects(text, kind):
    with pytest.raises(actions.InvalidAction) as exc:
        actions.parse(text)
    assert exc.value.kind == kind


def test_check_code():
    actions.check_code("import sys, collections\nfrom itertools import groupby\n", 1000)
    for code, kind in [("", "missing_code"), ("x" * 2000, "code_too_large"), ("def f(:\n", "syntax_error"),
                       ("import numpy\n", "non_stdlib_import")]:
        with pytest.raises(actions.InvalidAction) as exc:
            actions.check_code(code, 1000)
        assert exc.value.kind == kind


def test_cost_estimate_and_unknowns():
    u = Usage(input_tokens=10_000, cached_input_tokens=2_000, output_tokens=30_000, reasoning_tokens=25_000, source="reported")
    cost, status, version = estimate_cost("openai_responses", "gpt-6.1-sol", u, request_sent=True)
    assert status == "estimated" and version.startswith("openai/gpt-6.1-sol")
    assert cost == pytest.approx((8_000 * 2 + 2_000 * 0.1 + 30_000 * 10) / 1e6)
    assert estimate_cost("openai_responses", "gpt-6.1-sol", Usage(), request_sent=True)[:2] == (None, "unknown")
    assert estimate_cost("openai_responses", "gpt-6.1-sol", Usage(), request_sent=False)[:2] == (0.0, "not_billed")
    assert estimate_cost("chat_compat", "qwen", Usage(), request_sent=True,
                         base_url="http://127.0.0.1:11434/v1")[1] == "local_no_api_fee"


def test_hosted_qwen_cost_is_not_reported_as_free():
    args = ("chat_compat", "Qwen3.8-27B", Usage(input_tokens=100, output_tokens=50, source="reported"))
    assert estimate_cost(*args, request_sent=True, base_url="https://aiping.cn/api/v1") == (None, "unknown", None)
    assert estimate_cost(*args, request_sent=False, base_url="https://aiping.cn/api/v1") == (0.0, "not_billed", None)
