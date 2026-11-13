"""Common result type for model calls. Unknown usage stays None; it is never coerced to zero."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..config import ModelConfig


@dataclass
class Usage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    source: str = "unknown"  # reported | unknown | not_applicable
    raw: dict | None = None


@dataclass
class LLMResult:
    ok: bool
    text: str | None
    usage: Usage
    latency_s: float
    model_returned: str | None = None
    request_id: str | None = None
    # timeout | network | rate_limit | http_4xx | http_5xx | incomplete | refusal | bad_response | config
    error_kind: str | None = None
    error_message: str | None = None
    request_body: dict = field(default_factory=dict)
    response_body: dict | str | None = None


class LLMClient(Protocol):
    config: ModelConfig

    def complete(self, system: str, user: str, schema: dict, timeout_s: float, max_output_tokens: int) -> LLMResult: ...


def classify_http(status: int) -> str:
    if status == 429:
        return "rate_limit"
    return "http_5xx" if status >= 500 else "http_4xx"
