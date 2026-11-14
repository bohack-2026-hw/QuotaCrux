"""OpenAI Responses API client (GPT-6.1 Sol, reasoning effort xhigh)."""

from __future__ import annotations

import os
import time

import httpx

from ..config import ModelConfig
from .base import LLMResult, Usage, classify_http


class OpenAIResponsesClient:
    def __init__(self, cfg: ModelConfig):
        self.config = cfg

    def complete(self, system: str, user: str, schema: dict, timeout_s: float, max_output_tokens: int) -> LLMResult:
        cfg = self.config
        body = {
            "model": cfg.model,
            "instructions": system,
            "input": user,
            "max_output_tokens": max_output_tokens,
            "store": False,
            "text": {"format": {"type": "json_schema", "name": "agent_action", "schema": schema, "strict": True}},
        }
        if cfg.reasoning_effort:
            body["reasoning"] = {"effort": cfg.reasoning_effort}
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return LLMResult(False, None, Usage(source="not_applicable"), 0.0, error_kind="config",
                             error_message="OPENAI_API_KEY is not set", request_body=body)

        t0 = time.perf_counter()
        try:
            resp = httpx.post(
                f"{cfg.base_url.rstrip('/')}/responses",
                json=body,
                headers={"Authorization": f"Bearer {key}"},
                timeout=httpx.Timeout(timeout_s, connect=min(10.0, timeout_s)),
            )
        except httpx.TimeoutException as exc:
            return LLMResult(False, None, Usage(), time.perf_counter() - t0, error_kind="timeout",
                             error_message=f"no response within {timeout_s:.0f}s ({type(exc).__name__}); usage unknown, may still be billed",
                             request_body=body)
        except httpx.HTTPError as exc:
            return LLMResult(False, None, Usage(), time.perf_counter() - t0, error_kind="network",
                             error_message=f"{type(exc).__name__}: {exc}", request_body=body)
        latency = time.perf_counter() - t0
        request_id = resp.headers.get("x-request-id")
        try:
            data = resp.json()
        except ValueError:
            return LLMResult(False, None, Usage(), latency, request_id=request_id, error_kind="bad_response",
                             error_message=f"HTTP {resp.status_code}, non-JSON body", request_body=body, response_body=resp.text[:4000])
        usage = _usage(data.get("usage"))
        if resp.status_code >= 400:
            err = data.get("error") or {}
            return LLMResult(False, None, usage, latency, request_id=request_id, error_kind=classify_http(resp.status_code),
                             error_message=f"HTTP {resp.status_code}: {err.get('message') or str(data)[:500]}",
                             request_body=body, response_body=data)

        text_parts, refusal = [], None
        for item in data.get("output") or []:
            if item.get("type") != "message":
                continue
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    text_parts.append(c.get("text", ""))
                elif c.get("type") == "refusal":
                    refusal = c.get("refusal")
        text = "".join(text_parts) or None
        result = LLMResult(True, text, usage, latency, model_returned=data.get("model"), request_id=request_id,
                           request_body=body, response_body=data)
        if data.get("status") == "incomplete":
            reason = (data.get("incomplete_details") or {}).get("reason")
            result.ok, result.error_kind = False, "incomplete"
            result.error_message = f"response incomplete ({reason}); visible output {'present' if text else 'empty'}"
        elif refusal:
            result.ok, result.error_kind, result.error_message = False, "refusal", refusal
        elif not text:
            result.ok, result.error_kind, result.error_message = False, "bad_response", "no output_text in response"
        return result


def _usage(u: dict | None) -> Usage:
    if not u:
        return Usage()
    in_d = u.get("input_tokens_details") or {}
    out_d = u.get("output_tokens_details") or {}
    write_key = next((k for k in in_d if "write" in k or "creation" in k), None)
    return Usage(
        input_tokens=u.get("input_tokens"),
        cached_input_tokens=in_d.get("cached_tokens"),
        cache_write_tokens=in_d.get(write_key) if write_key else None,
        output_tokens=u.get("output_tokens"),
        reasoning_tokens=out_d.get("reasoning_tokens"),
        source="reported",
        raw=u,
    )
