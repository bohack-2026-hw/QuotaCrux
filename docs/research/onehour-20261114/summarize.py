#!/usr/bin/env python3
"""Summarize exported one-hour ALE runs without importing the product runtime.

Input: --batch HOST=/path/batch.json (repeat), optional --reports HOST=/export/root.
Each batch has runs: [{variant, run_id, report_path?}], retaining failed slots.
Output: summary.json, summary.csv, and interrupted_attempts.csv. Quality results
stay host-stratified; spend includes both planned runs and interrupted attempts.
Frozen token pricing follows routing_ablation.costs, including partial usage.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


VARIANTS = ("fixed_small", "fixed_large", "adaptive_rule", "action_decisions")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")
DEFAULT_FREEZE = Path(__file__).resolve().parents[1] / "native-routing/20261114/ale-short-freeze.json"


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def host_path(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("use HOST=/absolute/path")
    host, path = value.split("=", 1)
    if not host or not path:
        raise argparse.ArgumentTypeError("HOST and path must be nonempty")
    return host, Path(path).resolve()


def known_sum(values):
    known = [x for x in values if x is not None]
    return sum(known) if known else None


def unknown_calls(usage, key):
    return usage.get(key + "_unknown_calls", usage.get("requests", 1) if usage.get(key) is None else 0)


def combine_usage(items):
    result = {"requests": sum(x.get("requests", 0) for x in items),
              "ok": sum(x.get("ok", 0) for x in items),
              "latency_s": known_sum([x.get("latency_s") for x in items]) if items else 0}
    result["errors"] = dict(sum((Counter(x.get("errors", {})) for x in items), Counter()))
    for key in TOKENS:
        result[key] = known_sum([x.get(key) for x in items]) if items else 0
        result[key + "_unknown_calls"] = sum(unknown_calls(x, key) for x in items)
    return result


def combine_models(rows):
    keys = sorted({key for row in rows for key in row.get("usage_by_model", {})})
    return {key: combine_usage([row["usage_by_model"][key] for row in rows
                                if key in row.get("usage_by_model", {})]) for key in keys}


def combine_roles(ledgers):
    roles = {"small", "large", "router_action", "router_model"} | {key.split(":", 1)[0] for key in ledgers}
    return {role: combine_usage([usage for key, usage in ledgers.items() if key.split(":", 1)[0] == role])
            for role in sorted(roles)}


def token_cost(usage, snapshot):
    result = {"amount": None, "known_amount": None,
              "currency": snapshot["currency"] if snapshot else None, "status": "unknown"}
    if usage.get("requests") == 0:
        return {**result, "amount": 0.0, "known_amount": 0.0, "status": "no_model_calls"}
    if snapshot is None:
        return result
    missing = any(usage.get(key) is None or usage.get(key + "_unknown_calls", 0)
                  for key in ("input_tokens", "output_tokens"))
    known = any(usage.get(key) is not None for key in ("input_tokens", "output_tokens"))
    if known:
        value = sum(Decimal(str(usage.get(key) or 0)) * Decimal(str(snapshot[rate]))
                    for key, rate in (("input_tokens", "input_per_1m"),
                                      ("output_tokens", "output_per_1m"))) / Decimal(1_000_000)
        result.update(known_amount=float(value), status="partial" if missing else "estimated")
        if not missing:
            result["amount"] = float(value)
    return result


def costs(ledgers, prices):
    by_model = {}
    for key, usage in ledgers.items():
        role, provider, model = key.split(":", 2)
        purpose = "routing" if role in ("router_action", "router_model") else "generation"
        snapshot = prices.get("decisions" if purpose == "routing" else role)
        if snapshot and snapshot["model"] != model:
            snapshot = None
        by_model[key] = {**token_cost(usage, snapshot), "role": role, "provider": provider,
                         "model": model, "purpose": purpose,
                         "input_unknown_calls": unknown_calls(usage, "input_tokens"),
                         "output_unknown_calls": unknown_calls(usage, "output_tokens")}
    currencies = {}
    for currency in ("CNY", "USD"):
        items = [x for x in by_model.values() if x["currency"] == currency]
        unknown = sum(x["amount"] is None for x in items)
        subtotal = known_sum([x["known_amount"] for x in items]) if items else 0.0
        currencies[currency] = {
            "amount": sum(x["amount"] for x in items) if not unknown else None,
            "known_amount": subtotal,
            "status": "partial" if unknown and subtotal is not None else "unknown" if unknown else "estimated" if items else "no_model_calls",
            "unknown_model_ledgers": unknown,
            "input_unknown_calls": sum(x["input_unknown_calls"] for x in items),
            "output_unknown_calls": sum(x["output_unknown_calls"] for x in items),
        }
    return {"by_model": by_model, "by_currency": currencies,
            "unpriced_model_ledgers": sum(x["currency"] is None for x in by_model.values()),
            "note": "Frozen token-price estimate, not a bill. CNY and USD are never added. Cached input uses the frozen input rate; reasoning is already part of output. Missing usage stays unknown."}


def find_report(row, batch_path, export_root):
    candidates = []
    run_id = row.get("run_id")
    if run_id:
        for root in (export_root, batch_path.parent):
            if root is not None:
                candidates.extend(root / suffix for suffix in (
                    f"var/runs/{run_id}/report.json", f"runs/{run_id}/report.json",
                    f"{run_id}/report.json"))
    if row.get("report_path"):
        p = Path(row["report_path"])
        candidates.append(p if p.is_absolute() else batch_path.parent / p)
    return next((p.resolve() for p in candidates if p.is_file()), None)


def protocol_warnings(rep, variant, freeze, execution):
    result = []
    cfg, task = rep["config"], rep["task"]
    protocol, routing = cfg["research_protocol"], cfg["routing"]
    checks = {
        "mode=eval": rep["mode"] == "eval", "snapshot=v0": rep["snapshot_id"] == "v0",
        "research_mode=feedback": protocol["mode"] == "feedback",
        "final enabled": protocol["final_evaluation"] is True,
        "360 second loop": cfg["limits"]["wall_clock_s"] == 360,
        "20 total model requests": cfg["limits"]["max_model_requests"] == 20,
        "10 candidates": cfg["limits"]["max_candidates"] == 10,
        "5 development cases": task["dev_params"]["cases"] == 5,
        "15 final cases": task["final_params"]["cases"] == 15,
        "native ahc026": "ahc026" in task["task_id"],
        "model routing=rule": routing["model"] == "rule",
        "action routing matches treatment": routing["action"] == ("decisions" if variant == "action_decisions" else "llm"),
        "fixed model matches treatment": protocol["fixed_model"] == (variant.removeprefix("fixed_") if variant.startswith("fixed_") else None),
        "model policy matches treatment": protocol["model_policy"] == ("fixed" if variant.startswith("fixed_") else "adaptive"),
        "no scripted model": not rep.get("scripted_model"),
    }
    frozen_task = freeze.get("tasks", {}).get(task["task_id"])
    if execution and execution.get("task_id") == task["task_id"]:
        checks["task manifest matches execution freeze"] = cfg["task_manifest_sha256"] == execution["task_manifest_sha256"]
        checks["source task manifest matches price/protocol freeze"] = execution["source_task_manifest_sha256"] in {
            item["manifest_sha256"] for item in freeze.get("tasks", {}).values()}
        checks["frozen prices unchanged"] = execution["price_snapshots"] == freeze["price_snapshots"]
    elif frozen_task:
        checks["task manifest matches freeze"] = cfg["task_manifest_sha256"] == frozen_task["manifest_sha256"]
    else:
        result.append("task ID absent from supplied freeze; compare task manifests before claiming same task")
    for label, passed in checks.items():
        if not passed:
            result.append("protocol mismatch: " + label)
    return result


def summarize_run(host, slot, row, batch_path, export_root, freeze, execution=None):
    variant = row.get("variant")
    if variant not in VARIANTS:
        raise ValueError(f"{host} slot {slot}: unknown variant {variant!r}")
    result = {"host": host, "seq": row.get("seq", slot), "variant": variant,
              "run_id": row.get("run_id"), "batch_status": row.get("status"),
              "batch_error": row.get("error"), "report_available": False, "warnings": []}
    path = find_report(row, batch_path, export_root)
    if path is None:
        result.update(status=row.get("status", "not_run"), final_status="unknown",
                      final_score=None, c0_final_score=None, gain_score=None, gain_percent=None)
        result["warnings"].append("report.json unavailable; this attempt and its costs remain unknown")
        return result
    rep = read_json(path)
    if row.get("run_id") and rep["run_id"] != row["run_id"]:
        raise ValueError(f"run ID mismatch in {path}")
    out, timing, it = rep["outcome"], rep["timing"], rep["iterations"]
    usage = rep["usage"]["by_model"]
    final = rep.get("final_evaluation")
    valid = bool(final and final.get("status") == "passed" and final.get("correct"))
    objective = (final or {}).get("objective") or out.get("final_objective") or {}
    score, baseline = (objective.get("value") if valid else None), objective.get("baseline")
    gain = score - baseline if score is not None and baseline is not None else None
    result.update(
        report_available=True, report_path=str(path), report_sha256=sha256(path),
        run_id=rep["run_id"], status=rep["status"], recorded_status=rep.get("recorded_status"),
        stop_reason=rep.get("stop_reason"), stop_detail=rep.get("stop_detail"),
        task_id=rep["task"]["task_id"], final_status=out.get("final_status"), final_correct=valid,
        final_score=score, c0_final_score=baseline, gain_score=gain,
        gain_percent=100 * gain / baseline if gain is not None and baseline else None,
        final_case_count=(final or {}).get("case_count"),
        final_passed_cases=(final or {}).get("passed_cases"),
        best_candidate_id=(rep.get("best_candidate") or {}).get("candidate_id"),
        best_is_initial=out.get("best_is_initial"),
        loop_s=timing.get("agent_loop_elapsed_s", timing.get("agent_loop_s")),
        total_s=timing.get("wall_clock_total_s"), final_s=timing.get("final_evaluation_s"),
        model_wait_s=timing.get("model_wait_s"), dev_evaluation_s=timing.get("dev_evaluation_s"),
        requests=it["model_requests"], generation_requests=it.get("generation_requests"),
        routing_requests=it.get("routing_requests"), small_requests=it.get("small_model_requests"),
        large_requests=it.get("large_model_requests"), upgrades=it.get("upgrades"),
        candidates_proposed=it["candidates_proposed"], candidates_passed=it["candidates_passed"],
        candidate_valid_rate=it["candidates_passed"] / it["candidates_proposed"] if it["candidates_proposed"] else None,
        usage_total=rep["usage"]["total"], usage_by_model=usage, usage_by_role=combine_roles(usage),
        cost=costs(usage, freeze["price_snapshots"]),
        started_at=rep.get("started_at"), ended_at=rep.get("ended_at"),
        actual_protocol=rep["config"]["research_protocol"], actual_routing=rep["config"]["routing"],
        config_fingerprint=rep.get("config_fingerprint"),
        task_manifest_sha256=rep["config"]["task_manifest_sha256"],
        environment=rep["environment"])
    result["warnings"].extend(protocol_warnings(rep, variant, freeze, execution))
    counted = sum(item["requests"] for item in usage.values())
    if counted != it["model_requests"]:
        result["warnings"].append(f"request accounting mismatch: by_model={counted}, iterations={it['model_requests']}")
    if valid and ((final or {}).get("case_count") != 15 or (final or {}).get("passed_cases") != 15):
        result["warnings"].append("passed final does not contain 15/15 passed cases")
    return result


def distribution(values):
    values = [x for x in values if x is not None]
    return {"n": len(values), "values": values, "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def summarize_host(rows, freeze):
    available = [r for r in rows if r["report_available"]]
    missing = len(rows) - len(available)
    ledgers = combine_models(available)
    grouped = {}
    for variant in VARIANTS:
        items = [r for r in rows if r["variant"] == variant]
        if not items:
            continue
        observed = [r for r in items if r["report_available"]]
        grouped[variant] = {"planned": len(items), "reports": len(observed),
                            "final_passed": sum(r.get("final_correct", False) for r in observed),
                            "metrics": {key: distribution([r.get(key) for r in observed]) for key in
                                        ("final_score", "gain_score", "gain_percent", "loop_s", "total_s", "requests", "candidate_valid_rate")},
                            "cost_observed_reports_only": costs(combine_models(observed), freeze["price_snapshots"])}
    warnings = []
    if missing:
        warnings.append(f"{missing} planned slots lack reports; aggregates below cover exported reports only")
    for key in ("task_manifest_sha256",):
        if len({r[key] for r in available}) > 1:
            warnings.append(f"within-host {key} differs")
    environments = {json.dumps(r["environment"], sort_keys=True) for r in available}
    if len(environments) > 1:
        warnings.append("within-host runtime environments differ; inspect per-run environment")
    paired = []
    baselines = [r for r in available if r["variant"] == "adaptive_rule"]
    if len(baselines) == 1:
        baseline = baselines[0]
        for r in available:
            if r["variant"] == "adaptive_rule":
                continue
            a, b = r.get("final_score"), baseline.get("final_score")
            paired.append({"variant": r["variant"], "baseline": "adaptive_rule",
                           "score_difference": a-b if a is not None and b is not None else None,
                           "total_seconds_difference": r["total_s"]-baseline["total_s"] if r["total_s"] is not None and baseline["total_s"] is not None else None,
                           "requests_difference": r["requests"]-baseline["requests"]})
    return {"planned": len(rows), "reports": len(available), "missing_reports": missing,
            "final_passed": sum(r.get("final_correct", False) for r in available),
            "run_statuses": dict(Counter(r["status"] for r in rows)),
            "usage_by_model": ledgers, "usage_by_role": combine_roles(ledgers),
            "cost_observed_reports_only": costs(ledgers, freeze["price_snapshots"]),
            "variants": grouped, "descriptive_differences": paired, "warnings": warnings}


def all_attempts_cost(rows, freeze):
    observed = [row for row in rows if row["report_available"]]
    result = costs(combine_models(observed), freeze["price_snapshots"])
    unmatched = sum(row.get("unmatched_started_calls", 0) for row in rows)
    missing = len(rows) - len(observed)
    result.update(requests_recorded=sum(row["requests"] for row in observed),
                  unmatched_started_calls=unmatched, missing_reports=missing,
                  scope="All exported planned and interrupted attempts; known subtotals cover recorded calls only.",
                  extra_cost_note="Started requests without a completed ledger may incur additional charges; their tokens and cost are unknown.")
    for currency in result["by_currency"].values():
        currency["recorded_calls_amount"] = currency["amount"]
        currency["recorded_calls_status"] = currency["status"]
        if unmatched or missing or result["unpriced_model_ledgers"]:
            currency["amount"] = None
            currency["status"] = ("partial" if currency["known_amount"] is not None
                                  and currency["recorded_calls_status"] != "no_model_calls" else "unknown")
    result["complete"] = all(item["amount"] is not None for item in result["by_currency"].values())
    return result


def write_csv(path, rows):
    fields = ["host", "seq", "variant", "run_id", "status", "final_status", "final_score", "c0_final_score",
              "gain_score", "gain_percent", "loop_s", "total_s", "requests", "small_requests", "large_requests",
              "routing_requests", "candidates_passed", "candidates_proposed", "candidate_valid_rate",
              "CNY_known", "CNY_status", "CNY_unknown_ledgers", "USD_known", "USD_status", "USD_unknown_ledgers",
              "unpriced_model_ledgers", "unmatched_started_calls", "stop_reason", "warnings"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {key: row.get(key) for key in fields}
            unpriced = row.get("cost", {}).get("unpriced_model_ledgers")
            for currency in ("CNY", "USD"):
                cost = row.get("cost", {}).get("by_currency", {}).get(currency, {})
                if row.get("report_available") and (not cost or cost.get("status") == "no_model_calls"):
                    cost = ({"known_amount": 0, "status": "no_model_calls", "unknown_model_ledgers": 0}
                            if unpriced == 0 else {"known_amount": None, "status": "unknown"})
                if row.get("unmatched_started_calls", 0) and row.get("report_available"):
                    cost = {**cost, "status": "partial" if cost.get("known_amount") is not None
                            and cost.get("status") != "no_model_calls" else "unknown"}
                out.update({f"{currency}_known": cost.get("known_amount"), f"{currency}_status": cost.get("status", "missing_report"),
                            f"{currency}_unknown_ledgers": cost.get("unknown_model_ledgers")})
            out["unpriced_model_ledgers"] = unpriced
            out["warnings"] = "; ".join(row["warnings"])
            writer.writerow(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="append", type=host_path, required=True)
    parser.add_argument("--reports", action="append", type=host_path, default=[])
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    roots = dict(args.reports)
    freeze = read_json(args.freeze)
    for role, price in freeze["price_snapshots"].items():
        if price["unit"] != "per_1m_tokens" or price["currency"] not in ("CNY", "USD"):
            raise ValueError(f"unsupported frozen price for {role}")
        for rate in ("input_per_1m", "output_per_1m"):
            if not math.isfinite(float(price[rate])) or price[rate] < 0:
                raise ValueError(f"invalid frozen rate {role}/{rate}")
    rows, interrupted, batches, grouped = [], [], [], defaultdict(list)
    seen = set()
    for host, path in args.batch:
        batch = read_json(path)
        slots = batch.get("runs")
        if not isinstance(slots, list) or not slots:
            raise ValueError(f"{path}: require nonempty runs array, including unexecuted slots")
        interrupted_slots = batch.get("interrupted_attempts", [])
        if not isinstance(interrupted_slots, list):
            raise ValueError(f"{path}: interrupted_attempts must be an array")
        execution_path = next((path.parent / name for name in ("execution-freeze.json", "preflight.json")
                               if (path.parent / name).is_file()), None)
        execution = read_json(execution_path) if execution_path else {}
        source = batch.get("source_commit", batch.get("source", batch.get("experiment_sha", execution.get("source_commit"))))
        batches.append({"host": host, "path": str(path), "sha256": sha256(path), "source_commit": source,
                        "execution_freeze": {"path": str(execution_path), "sha256": sha256(execution_path),
                            "task_id": execution.get("task_id"), "task_manifest_sha256": execution.get("task_manifest_sha256"),
                            "source_task_manifest_sha256": execution.get("source_task_manifest_sha256"),
                            "plan": execution.get("plan")} if execution_path else None,
                        "batch_metadata": {k: v for k, v in batch.items() if k not in ("runs", "plan", "interrupted_attempts")}})
        for kind, entries in (("planned_run", slots), ("interrupted_attempt", interrupted_slots)):
            for index, slot in enumerate(entries, 1):
                row = summarize_run(host, index, slot, path, roots.get(host), freeze, execution)
                row["record_kind"] = kind
                row["included_in_quality_comparison"] = kind == "planned_run"
                row["unmatched_started_calls"] = 0
                identity = (host, row["run_id"]) if row["run_id"] else (host, str(path), kind, index)
                if identity in seen:
                    raise ValueError(f"duplicate exported run: {identity}")
                seen.add(identity)
                if source and str(source)[:7] != str(freeze["experiment_sha"])[:7]:
                    row["warnings"].append(f"source commit differs from freeze: {source}")
                if source is None:
                    row["warnings"].append("source_commit absent from batch and adjacent execution-freeze/preflight")
                if kind == "interrupted_attempt":
                    row["interruption"] = slot["interruption"]
                    unmatched = row["interruption"]["unmatched_started_calls"]
                    if not isinstance(unmatched, int) or isinstance(unmatched, bool) or unmatched < 0:
                        raise ValueError(f"{path}: unmatched_started_calls must be a nonnegative integer")
                    row["unmatched_started_calls"] = unmatched
                    if unmatched:
                        row["warnings"].append(f"{unmatched} started requests lack completed usage ledgers and may incur additional charges; cost covers recorded calls only")
                    interrupted.append(row)
                else:
                    rows.append(row)
                    grouped[host].append(row)
    all_attempts = rows + interrupted
    hosts = {}
    for host, items in grouped.items():
        host_attempts = [row for row in all_attempts if row["host"] == host]
        hosts[host] = {**summarize_host(items, freeze),
                       "interrupted_attempts": sum(row["record_kind"] == "interrupted_attempt" for row in host_attempts),
                       "unmatched_started_calls": sum(row["unmatched_started_calls"] for row in host_attempts),
                       "all_attempts_observed_cost": all_attempts_cost(host_attempts, freeze)}
    summary = {
        "schema": "onehour_ale_summary/1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "freeze_path": str(args.freeze.resolve()), "freeze_sha256": sha256(args.freeze),
        "price_snapshots": freeze["price_snapshots"], "input_batches": batches,
        "scope": "Exploratory one-hour supplement. Host-stratified descriptive results only; no pooled speedup or statistical superiority claim.",
        "definitions": {"gain_percent": "100 * (valid final score - paired final c0 score) / paired final c0 score",
                        "candidate_valid_rate": "model candidates passing development validation / model candidates proposed; c0 excluded",
                        "loop_s": "research-loop elapsed time", "total_s": "whole run including final evaluation",
                        "cost_known": "known token-price subtotal; incomplete totals remain null, never zero-filled",
                        "quality_comparison": "runs contains only the planned comparison cells; interrupted attempts are reported separately",
                        "all_attempts_observed_cost": "includes interrupted-attempt recorded usage; unmatched started calls may add unknown charges",
                        "reasoning_tokens": "subset of output tokens; never added again to input+output or billing"},
        "hosts": hosts, "runs": rows, "interrupted_attempts": interrupted,
        "unmatched_started_calls": sum(row["unmatched_started_calls"] for row in all_attempts),
        "all_attempts_observed_cost": all_attempts_cost(all_attempts, freeze)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_csv(args.out / "summary.csv", rows)
    write_csv(args.out / "interrupted_attempts.csv", interrupted)
    print(json.dumps({"out": str(args.out.resolve()), "hosts": len(grouped), "planned": len(rows),
                      "reports": sum(r["report_available"] for r in rows),
                      "interrupted_attempts": len(interrupted),
                      "unmatched_started_calls": summary["unmatched_started_calls"],
                      "warning_count": sum(len(r["warnings"]) for r in all_attempts)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.exit(f"onehour_summarize: {exc}")
