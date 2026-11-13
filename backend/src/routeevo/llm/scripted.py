"""Scripted stand-in model for functional checks only. Runs using it are labelled and never count as model results.

A script is JSON: {"small": [action, ...], "large": [action, ...]}. Each action is the dict the real model
would return; missing fields default to null. `code_file` (relative to the script) may replace `code`.
An entry {"raw": "<text>"} returns that text verbatim (e.g. to test invalid JSON); {"error": "<kind>"} simulates
a failed request. When a role's list is exhausted it returns a finish action.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import ModelConfig
from .base import LLMResult, Usage


class ScriptedClient:
    def __init__(self, cfg: ModelConfig, script_path: Path):
        self.config = cfg
        script = json.loads(script_path.read_text())
        self._queue = list(script.get(cfg.role, []))
        self._base = script_path.parent

    def complete(self, system: str, user: str, schema: dict, timeout_s: float, max_output_tokens: int) -> LLMResult:
        body = {"scripted_role": self.config.role, "max_output_tokens": max_output_tokens}
        usage = Usage(source="not_applicable")
        if not self._queue:
            action = {"action": "finish", "purpose": "脚本已用完", "expected_result": "结束", "verification": "无",
                      "finish_reason": "scripted model has no more actions"}
            return LLMResult(True, json.dumps(action, ensure_ascii=False), usage, 0.0, model_returned="scripted", request_body=body)
        entry = dict(self._queue.pop(0))
        if "error" in entry:
            return LLMResult(False, None, usage, 0.0, model_returned="scripted", error_kind=entry["error"],
                             error_message=f"scripted {entry['error']}", request_body=body)
        if "raw" in entry:
            return LLMResult(True, entry["raw"], usage, 0.0, model_returned="scripted", request_body=body)
        if "code_file" in entry:
            entry["code"] = (self._base / entry.pop("code_file")).read_text()
        return LLMResult(True, json.dumps(entry, ensure_ascii=False), usage, 0.0, model_returned="scripted", request_body=body)
