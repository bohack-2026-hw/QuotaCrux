"""Chat Completions-compatible client for local and hosted Qwen services."""

from __future__ import annotations

import os
import re
import time

import httpx

from ..config import ModelConfig
from .base import LLMResult, Usage, classify_http

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class ChatCompatClient:
    def __init__(self, cfg: ModelConfig):
        self.config = cfg

    def complete(self, system: str, user: str, schema: dict, timeout_s: float, max_output_tokens: int) -> LLMResult:
        cfg = self.config
        body: dict = {
            "model": cfg.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        if cfg.reasoning_effort:
            body["reasoning_effort"] = cfg.reasoning_effort
        if cfg.enable_thinking is not None:
            body["enable_thinking"] = cfg.enable_thinking
        if cfg.temperature is not None:
            body["temperature"] = cfg.temperature
        if cfg.response_format == "json_object":
            body["response_format"] = {"type": "json_object"}
        elif cfg.response_format == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "agent_action", "schema": schema, "strict": True}}
        headers = {}
        if os.environ.get("QWEN_API_KEY"):
            headers["Authorization"] = f"Bearer {os.environ['QWEN_API_KEY']}"

        t0 = time.perf_counter()
        try:
            resp = httpx.post(f"{cfg.base_url.rstrip('/')}/chat/completions", json=body, headers=headers,
                              timeout=httpx.Timeout(timeout_s, connect=min(10.0, timeout_s)))
        except httpx.TimeoutException as exc:
            return LLMResult(False, None, Usage(), time.perf_counter() - t0, error_kind="timeout",
                             error_message=f"no response within {timeout_s:.0f}s ({type(exc).__name__})", request_body=body)
        except httpx.HTTPError as exc:
            return LLMResult(False, None, Usage(), time.perf_counter() - t0, error_kind="network",
                             error_message=f"{type(exc).__name__}: {exc}", request_body=body)
        latency = time.perf_counter() - t0
        try:
            data = resp.json()
        except ValueError:
            return LLMResult(False, None, Usage(), latency, error_kind="bad_response",
                             error_message=f"HTTP {resp.status_code}, non-JSON body", request_body=body, response_body=resp.text[:4000])
        usage = _usage(data.get("usage"))
        request_id = data.get("id") or resp.headers.get("x-request-id")
        if resp.status_code >= 400:
            err = data.get("error")
            msg = err.get("message") if isinstance(err, dict) else err
            return LLMResult(False, None, usage, latency, request_id=request_id, error_kind=classify_http(resp.status_code),
                             error_message=f"HTTP {resp.status_code}: {msg or str(data)[:500]}", request_body=body, response_body=data)
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        text = _THINK.sub("", content).strip() or None
        result = LLMResult(True, text, usage, latency, model_returned=data.get("model"), request_id=request_id,
                           request_body=body, response_body=data)
        if choice.get("finish_reason") == "length":
            result.ok, result.error_kind = False, "incomplete"
            result.error_message = f"hit max_tokens={max_output_tokens}; visible output {'present' if text else 'empty'}"
        elif not text:
            result.ok, result.error_kind, result.error_message = False, "bad_response", "empty message content"
        return result


def _usage(u: dict | None) -> Usage:
    if not u:
        return Usage()
    details = u.get("completion_tokens_details") or {}
    prompt_details = u.get("prompt_tokens_details") or {}
    return Usage(
        input_tokens=u.get("prompt_tokens"),
        cached_input_tokens=prompt_details.get("cached_tokens"),
        output_tokens=u.get("completion_tokens"),
        reasoning_tokens=details.get("reasoning_tokens"),
        source="reported" if u.get("prompt_tokens") is not None else "unknown",
        raw=u,
    )
