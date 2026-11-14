"""Run the preregistered four-task pilot; keep account balances private."""

import argparse
import json
import os
import platform
import subprocess
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import httpx

from routeevo import config, db, evaluator, taskpkg
from routeevo.agent.runner import Runner, RunOptions, UPGRADE_RULE
from routeevo.llm.pricing import PRICE_TABLES
from routeevo.sandbox import executor


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def balance(label):
    response = httpx.get(
        "https://aiping.cn/api/v1/user/remain/points",
        headers={"Authorization": "Bearer " + os.environ["QWEN_API_KEY"]},
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError("AIPing balance query returned a nonzero code")
    data = body["data"]
    values = {k: str(data[k]) for k in ("total_remain", "gift_remain", "recharge_remain")}
    private = config.VAR_DIR / "private"
    private.mkdir(mode=0o700, exist_ok=True)
    path = private / f"balance-{label}.json"
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
        json.dump({"queried_at": db.now(), "values": values}, out)
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "run"))
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--pricing-snapshot", type=Path, required=True)
    args = parser.parse_args()
    config.load_dotenv(args.env_file)
    os.environ["ROUTEEVO_NO_DOTENV"] = "1"
    plan = json.loads((config.VAR_DIR / "plan.json").read_text())
    limits, measure = config.RunLimits(), config.MeasureConfig()
    if args.phase == "preflight":
        if (config.VAR_DIR / "preflight.json").exists():
            raise RuntimeError("preflight already recorded")
        checks = []
        for item in plan:
            task = taskpkg.load(item["task_id"])
            for dataset in ("dev", "final"):
                ev = evaluator.evaluate(task, task.initial_code.encode(), dataset, measure, limits, measure_timing=False)
                checks.append(asdict(ev))
                write(config.VAR_DIR / "preflight.json", checks)
                print(json.dumps({"preflight": item["problem"], "dataset": dataset, "status": ev.status,
                                  "duration_s": ev.detail.get("duration_s")}), flush=True)
                if ev.status != "passed":
                    raise RuntimeError("reference preflight failed; inspect preflight.json")
        return

    checks = json.loads((config.VAR_DIR / "preflight.json").read_text())
    if len(checks) != len(plan) * 2 or any(c["status"] != "passed" for c in checks):
        raise RuntimeError("complete reference preflight required")
    if db.one("SELECT 1 FROM runs"):
        raise RuntimeError("experiment DB already contains runs; do not silently repeat paid calls")
    cfgs = config.default_model_configs()
    price = json.loads(args.pricing_snapshot.read_text())
    if cfgs["small"].model != price["id"]:
        raise RuntimeError("pricing snapshot does not match small model")
    env = executor.environment_info(measure)
    manifest = {
        "started_at": db.now(),
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "mode": "eval", "snapshot_id": "v0", "plan": plan,
        "models": {r: c.public_dict() for r, c in cfgs.items()},
        "limits": limits.to_dict(), "measure": measure.to_dict(), "upgrade_rule": UPGRADE_RULE,
        "environment": env, "host_platform": platform.platform(), "host_python": platform.python_version(),
        "qwen_pricing": {"currency": "CNY", "unit": "per 1M tokens", "snapshot": price,
                         "sources": ["https://aiping.cn/api/v1/models", "https://aiping.cn/docs/UserGuide/pricing-rules"]},
        "openai_price_tables": PRICE_TABLES,
        "selection_note": "Fixed before model calls: cached shard, two io and two functional problems; one run each, 5 dev / 15 final.",
    }
    write(config.VAR_DIR / "experiment.json", manifest)
    results = []
    for index, item in enumerate(plan):
        before = balance(f"{index}-before")
        runner = Runner(RunOptions(task_id=item["task_id"], mode="eval", snapshot_id="v0", limits=limits,
                                   measure=measure, label="EffiBench-X real four-task pilot 2026-11-14"))
        run_id = runner.create()
        print(json.dumps({"started": item["problem"], "run_id": run_id, "at": db.now()}), flush=True)
        rep = runner.execute()
        after = balance(f"{index}-after")
        calls = [dict(r) for r in db.all_rows(
            "SELECT role, model_requested, model_returned, status, error_kind, usage_source, input_tokens, "
            "cached_input_tokens, output_tokens, reasoning_tokens, cost_usd, cost_status, latency_s, "
            "response_path FROM model_calls WHERE run_id = ? ORDER BY started_at", (run_id,))]
        for call in calls:
            response_path = call.pop("response_path")
            raw = json.loads(Path(response_path).read_text()) if response_path else {}
            response = raw.get("response") if isinstance(raw, dict) else None
            call["reported_usage"] = response.get("usage") if isinstance(response, dict) else None
        small = [c for c in calls if c["role"] == "small"]
        usage_known = all(c["input_tokens"] is not None and c["output_tokens"] is not None for c in small)
        rates = price["price"]
        estimated_cny = (sum(c["input_tokens"] * rates["input_price_range"][0]
                             + c["output_tokens"] * rates["output_price_range"][0] for c in small) / 1_000_000
                         if usage_known else None)
        delta = {k: str(Decimal(before[k]) - Decimal(after[k])) for k in before}
        result = {
            "problem": item["problem"], "task_id": item["task_id"], "run_id": run_id,
            "status": rep["status"], "stop_reason": rep["stop_reason"], "stop_detail": rep["stop_detail"],
            "outcome": rep["outcome"], "iterations": rep["iterations"], "timing": rep["timing"],
            "final_evaluation": rep["final_evaluation"], "usage": rep["usage"], "calls": calls,
            "qwen_standard_estimate_cny": estimated_cny,
            "qwen_account_balance_delta_cny": delta,
            "qwen_balance_note": "Account balance difference during this run; not a per-request invoice.",
            "final_speedup_including_initial": (1.0 if rep["outcome"]["best_is_initial"]
                                                and rep["outcome"]["final_correct"] else rep["outcome"]["final_speedup"]),
        }
        results.append(result)
        write(config.VAR_DIR / "results.json", results)
        print(json.dumps({"finished": item["problem"], "run_id": run_id, "outcome": result["outcome"],
                          "timing": result["timing"], "qwen_standard_estimate_cny": estimated_cny,
                          "qwen_balance_delta_cny": delta["total_remain"]}, ensure_ascii=False), flush=True)
    manifest["ended_at"] = db.now()
    write(config.VAR_DIR / "experiment.json", manifest)


if __name__ == "__main__":
    main()
