"""Run the pre-registered CPU pilot from backend/ using its .venv Python."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import subprocess

from routeevo import config, db, research_compare, taskpkg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task_ids", nargs=2)
    parser.add_argument("--dotenv", type=Path)
    parser.add_argument("--pricing", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError("pilot output already exists; use a new explicitly selected directory")
    if args.dotenv:
        config.load_dotenv(args.dotenv)
    models = config.default_model_configs()
    pricing = json.loads(args.pricing.read_text())
    if models["small"].model != pricing["id"]:
        raise ValueError("price snapshot must match the selected small model")
    tasks = [taskpkg.load(task_id) for task_id in args.task_ids]
    if [t.manifest["family"] for t in tasks] != ["ale-bench", "algotune"]:
        raise ValueError("pilot order is ALE-Bench followed by AlgoTune")
    limits = replace(config.RunLimits(), wall_clock_s=900, max_model_requests=20, max_candidates=10)
    args.out.mkdir(parents=True)
    manifest = {"started_at": db.now(), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "models": {k: v.public_dict() for k, v in models.items()}, "limits": limits.to_dict(),
        "measure": config.MeasureConfig().to_dict(), "host_platform": platform.platform(),
        "tasks": [t.manifest for t in tasks], "pricing": pricing,
        "price_source": "https://aiping.cn/api/v1/models", "price_currency": "CNY", "price_unit": "per 1M tokens",
        "protocol": "2 tasks x feedback/independent x 1 repeat; dev-only; fixed small model; empty snapshot v0"}
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    comparison = research_compare.execute(args.task_ids, repeats=1, limits=limits, fixed_model="small", final_evaluation=False,
        label="ALE-Bench and AlgoTune native pilot 2026-11-14")
    rates = pricing["price"]
    for run in comparison["runs"]:
        if "usage" not in run:
            continue
        usage = run["usage"]
        known = not usage["input_tokens_unknown_calls"] and not usage["output_tokens_unknown_calls"]
        run["estimated_cny"] = ((usage["input_tokens"] * rates["input_price_range"][0]
            + usage["output_tokens"] * rates["output_price_range"][0]) / 1_000_000) if known else None
        run["cost_note"] = "Standard CNY token-price estimate, not an invoice; discounts/account credits excluded."
    (args.out / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2))
    print(json.dumps({"comparison": comparison["comparison_id"], "status": comparison["status"],
                      "output": str(args.out)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
