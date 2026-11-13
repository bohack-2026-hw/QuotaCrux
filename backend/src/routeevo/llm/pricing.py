"""Versioned price tables. Costs are estimates from these tables unless a provider bill says otherwise."""

from __future__ import annotations

from .base import Usage

PRICE_TABLES = {
    "openai/gpt-6.1-sol/standard/2026-11-13": {
        "provider": "openai_responses",
        "model": "gpt-6.1-sol",
        "currency": "USD",
        "unit": "per 1M tokens",
        "input": 2.0,
        "cached_input": 0.10,
        "cache_write": 2.5,
        "output": 10.0,  # reasoning tokens are billed as output
        "long_context_threshold_input_tokens": 272_000,
        "long_context_multiplier": {"input": 2.0, "cached_input": 2.0, "cache_write": 2.0, "output": 1.5},
        "source": "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
        "retrieved": "2026-11-13",
    },
}


def price_version_for(provider: str, model: str) -> str | None:
    for version, table in PRICE_TABLES.items():
        if table["provider"] == provider and table["model"] == model:
            return version
    return None


def estimate_cost(provider: str, model: str, usage: Usage, request_sent: bool) -> tuple[float | None, str, str | None]:
    """Return (cost_usd, cost_status, price_version).

    cost_status: estimated | unknown | local_no_api_fee | not_applicable.
    """
    if provider == "scripted":
        return 0.0, "not_applicable", None
    if provider == "chat_compat":
        # Self-hosted Qwen: no API fee; machine cost is not accounted and is reported as unknown separately.
        return 0.0, "local_no_api_fee", None
    version = price_version_for(provider, model)
    if version is None:
        return None, "unknown", None
    if usage.source != "reported" or usage.input_tokens is None or usage.output_tokens is None:
        # A request that reached the provider may still be billed even if we never saw usage.
        return None, "unknown" if request_sent else "not_applicable", version
    t = PRICE_TABLES[version]
    cached = usage.cached_input_tokens or 0
    writes = usage.cache_write_tokens or 0
    uncached = max(usage.input_tokens - cached - writes, 0)
    long_ctx = usage.input_tokens > t["long_context_threshold_input_tokens"]
    mult = t["long_context_multiplier"] if long_ctx else {"input": 1, "cached_input": 1, "cache_write": 1, "output": 1}
    cost = (
        uncached * t["input"] * mult["input"]
        + cached * t["cached_input"] * mult["cached_input"]
        + writes * t["cache_write"] * mult["cache_write"]
        + usage.output_tokens * t["output"] * mult["output"]
    ) / 1_000_000
    return round(cost, 6), "estimated", version
