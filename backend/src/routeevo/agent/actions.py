"""The fixed action space and the program-side checks every model action passes before anything runs."""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass

ACTIONS = ("analyze", "get_evidence", "propose_candidate", "run_validation", "finish")
EVIDENCE_TOOLS = ("profile_candidate",)
_NULLABLE_STR = {"type": ["string", "null"]}

ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "purpose": {"type": "string"},
        "expected_result": {"type": "string"},
        "verification": {"type": "string"},
        "hypothesis": _NULLABLE_STR,
        "analysis": _NULLABLE_STR,
        "tool": {"type": ["string", "null"], "enum": [*EVIDENCE_TOOLS, None]},
        "candidate_id": _NULLABLE_STR,
        "parent_candidate_id": _NULLABLE_STR,
        "code": _NULLABLE_STR,
        "finish_reason": _NULLABLE_STR,
    },
    "required": [
        "action", "purpose", "expected_result", "verification", "hypothesis", "analysis",
        "tool", "candidate_id", "parent_candidate_id", "code", "finish_reason",
    ],
}

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_ALLOWED_TOP_MODULES = set(sys.stdlib_module_names) | {"__future__"}


@dataclass
class Action:
    action: str
    purpose: str
    expected_result: str
    verification: str
    hypothesis: str | None = None
    analysis: str | None = None
    tool: str | None = None
    candidate_id: str | None = None
    parent_candidate_id: str | None = None
    code: str | None = None
    finish_reason: str | None = None

    def params(self) -> dict:
        """Parameters worth storing on the step; code is stored as a candidate file instead."""
        return {k: v for k, v in {
            "tool": self.tool, "candidate_id": self.candidate_id, "parent_candidate_id": self.parent_candidate_id,
            "finish_reason": self.finish_reason, "analysis": self.analysis,
        }.items() if v is not None}


class InvalidAction(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def parse(text: str) -> Action:
    raw = text.strip()
    m = _FENCE.match(raw)
    if m:
        raw = m.group(1)
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise InvalidAction("not_json", "response is not a JSON object")
        raw = raw[start : end + 1]
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidAction("not_json", f"invalid JSON: {exc}") from None
    if not isinstance(obj, dict):
        raise InvalidAction("not_json", "response JSON is not an object")
    if obj.get("action") not in ACTIONS:
        raise InvalidAction("unknown_action", f"action must be one of {ACTIONS}, got {obj.get('action')!r}")
    fields = {k: obj.get(k) for k in Action.__dataclass_fields__}
    for k, v in fields.items():
        if v is not None and not isinstance(v, str):
            raise InvalidAction("bad_field", f"field {k!r} must be a string or null")
    for k in ("purpose", "expected_result", "verification"):
        if not (fields[k] or "").strip():
            raise InvalidAction("missing_field", f"field {k!r} is required")
    return Action(**fields)


def check_code(code: str | None, max_bytes: int) -> None:
    """Static checks only; the code is compiled, never executed, on the host."""
    if not code or not code.strip():
        raise InvalidAction("missing_code", "propose_candidate requires non-empty code")
    if len(code.encode()) > max_bytes:
        raise InvalidAction("code_too_large", f"code exceeds {max_bytes} bytes")
    try:
        tree = ast.parse(code, filename="candidate.py")
    except SyntaxError as exc:
        raise InvalidAction("syntax_error", f"SyntaxError: {exc}") from None
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for name in names:
            if name.split(".")[0] not in _ALLOWED_TOP_MODULES:
                raise InvalidAction("non_stdlib_import", f"only the Python standard library is available; found import {name!r}")
