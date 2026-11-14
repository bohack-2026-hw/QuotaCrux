"""Portable, read-only research comparison views and frozen-price estimates."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import json
import math
import re

from . import config

API_CONTRACT = "research-comparison-v1"
FINAL_STATUSES = ("disabled", "pending", "completed", "failed", "not_run")


def validate_pricing(snapshot: dict | None) -> None:
    if snapshot is None:
        return
    if not isinstance(snapshot, dict):
        raise ValueError("price snapshot must be an object")
    for key in ("model", "currency", "source", "retrieved_at"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key].strip():
            raise ValueError(f"price snapshot requires {key}")
    if snapshot.get("unit") != "per_1m_tokens":
        raise ValueError("price snapshot unit must be per_1m_tokens")
    if not re.fullmatch(r"[A-Z]{3}", snapshot["currency"]):
        raise ValueError("price snapshot currency must be a three-letter uppercase code")
    try:
        recorded = datetime.fromisoformat(snapshot["retrieved_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("price snapshot retrieved_at must be an ISO timestamp") from exc
    if recorded.tzinfo is None:
        raise ValueError("price snapshot retrieved_at must include a timezone")
    for key in ("input_per_1m", "output_per_1m"):
        value = snapshot.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"price snapshot {key} must be finite and nonnegative")


def estimate_cost(usage: dict, snapshot: dict | None) -> dict:
    """Unknown usage stays unknown; this is a token-price estimate, not a bill."""
    validate_pricing(snapshot)
    result = {"amount": None, "currency": snapshot["currency"] if snapshot else None,
              "status": "unknown", "source": snapshot["source"] if snapshot else None,
              "price_snapshot": deepcopy(snapshot)}
    if usage.get("requests") == 0:
        return {**result, "amount": 0.0, "status": "no_model_calls"}
    if snapshot is None or usage.get("requests") is None:
        return result
    if any(usage.get(f"{key}_unknown_calls", 0) or usage.get(key) is None
           for key in ("input_tokens", "output_tokens")):
        return result
    amount = sum(Decimal(str(usage[key])) * Decimal(str(snapshot[rate]))
                 for key, rate in (("input_tokens", "input_per_1m"), ("output_tokens", "output_per_1m"))) / 1_000_000
    return {**result, "amount": float(amount), "status": "estimated",
            "note": "Token-price estimate; cached input uses the frozen input rate; discounts and credits excluded."}


def _final_status(row: dict, enabled: bool) -> str:
    if not enabled:
        return "disabled"
    outcome = row.get("outcome") or {}
    final = row.get("final_evaluation")
    if outcome.get("final_error"):
        return "failed"
    if final:
        return "completed" if final.get("status") == "passed" and final.get("correct") else "failed"
    state = row.get("final_status") or outcome.get("final_status")
    if state in FINAL_STATUSES:
        return state
    # Earlier research JSON contains only the outcome, not the full final record.
    if outcome.get("final_evaluated"):
        return "completed" if outcome.get("final_correct") else "failed"
    return "pending" if row.get("status") in ("running", "pending") else "not_run"


def comparison_view(comparison: dict) -> dict:
    """Use embedded JSON only, so copied worker artifacts need no source DB."""
    out = deepcopy(comparison)
    if "comparison_id" not in out or not isinstance(out.get("runs"), list):
        raise ValueError("research comparison requires comparison_id and runs")
    if out.get("fair") is not None and not isinstance(out["fair"], bool):
        raise ValueError("comparison fair must be true, false or null")
    out["api_contract"] = API_CONTRACT
    out["fair"] = out.get("fair")
    out["dev_only"] = out.get("final_evaluation") is False
    snapshot = out.get("price_snapshot")
    validate_pricing(snapshot)
    routing_study = out.get("study") == "routing"
    if routing_study:
        for model_price in out.get("price_snapshots", {}).values():
            validate_pricing(model_price)
    for row in out["runs"]:
        row.setdefault("task", {"task_id": row["task_id"], "family": None, "objective": None})
        row["final_status"] = _final_status(row, not out["dev_only"])
        row["dev_status"] = (row.get("best_dev") or {}).get("status") or row.get("dev_status") or "not_run"
        if not routing_study:
            row.setdefault("cost", estimate_cost(row.get("usage") or {}, snapshot))
        if row["final_status"] == "failed" and row.get("status") == "completed":
            row["recorded_status"] = row["status"]
            row["status"] = "failed"
    if out.get("status") == "completed" and not out["dev_only"]:
        final_states = {row["final_status"] for row in out["runs"]}
        if "failed" in final_states:
            out["recorded_status"] = out["status"]
            out["status"] = "failed"
        elif final_states - {"completed"}:
            out["recorded_status"] = out["status"]
            out["status"] = "interrupted"
    return out


def _total_cost(comparison: dict) -> dict:
    if comparison.get("cost") is not None:
        return comparison["cost"]
    if comparison.get("study") == "routing":
        return {"by_currency": {}, "by_model": {}, "status": "unknown"}
    rows = comparison["runs"]
    result = estimate_cost({}, comparison.get("price_snapshot"))
    if not rows or any(row["cost"]["amount"] is None for row in rows):
        return result
    currencies = {row["cost"]["currency"] for row in rows}
    if len(currencies) != 1:
        return result
    return {**result, "amount": float(sum(Decimal(str(row["cost"]["amount"])) for row in rows)),
            "currency": next(iter(currencies)),
            "status": "no_model_calls" if all(row["cost"]["status"] == "no_model_calls" for row in rows) else "estimated"}


def comparison_summary(comparison: dict) -> dict:
    out = comparison_view(comparison)
    rows = out["runs"]
    return {"comparison_id": out["comparison_id"], "api_contract": API_CONTRACT,
            "protocol": out.get("protocol"), "study": out.get("study", "feedback"),
            "variants": list(dict.fromkeys(row["variant"] for row in rows if row.get("variant"))),
            "price_snapshots": out.get("price_snapshots"),
            "label": out.get("label"), "status": out.get("status"),
            "fair": out["fair"], "final_evaluation": out.get("final_evaluation"), "dev_only": out["dev_only"],
            "created_at": out.get("created_at"), "ended_at": out.get("ended_at"),
            "task_ids": list(dict.fromkeys(row["task_id"] for row in rows)),
            "tasks": list({row["task_id"]: row["task"] for row in rows}.values()),
            "modes": list(dict.fromkeys(row["mode"] for row in rows)), "runs_total": len(rows),
            "runs_finished": sum(row.get("status") in ("completed", "failed", "stopped", "interrupted") for row in rows),
            "final_status_counts": dict(Counter(row["final_status"] for row in rows)),
            "cost": _total_cost(out)}


def load(comparison_id: str) -> dict:
    if not re.fullmatch(r"research-[A-Za-z0-9_.-]+", comparison_id):
        raise KeyError(comparison_id)
    root = (config.VAR_DIR / "comparisons").resolve()
    path = root / f"{comparison_id}.json"
    if path.resolve().parent != root or not path.is_file():
        raise KeyError(comparison_id)
    comparison = json.loads(path.read_text())
    if not isinstance(comparison, dict) or comparison.get("comparison_id") != comparison_id:
        raise ValueError(f"comparison identity differs from {path.name}")
    return comparison_view(comparison)


def list_comparisons() -> list[dict]:
    paths = sorted((config.VAR_DIR / "comparisons").glob("research-*.json"), reverse=True)
    return [comparison_summary(load(path.stem)) for path in paths]
