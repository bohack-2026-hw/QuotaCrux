"""Synthetic routing-study comparison for frontend checks only (fixture: true; not an experimental result).

Builds rows in the shape routing_ablation.execute records, then runs the backend's own
routing_ablation.costs / summarize over them, so the JSON matches what
GET /api/research-comparisons/{id} serves for study="routing". Values are made up.
    uv run --directory backend python ../frontend/scripts/routing-fixture.py
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

# The backend's comparison lock imports fcntl; summarising needs no lock, so a stub lets this run on Windows.
sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))

from routeevo import routing_ablation as ra  # noqa: E402
from routeevo.research_views import comparison_view  # noqa: E402

OUT = Path(__file__).resolve().parent / "fixtures" / "routing-fixture.json"
TASKS = {
    "ale-bench-ahc026-fixture": {"family": "ale-bench", "objective": {"metric": "score", "direction": "maximize"}},
    "algotune-convolve_1d-fixture": {"family": "algotune", "objective": {"metric": "speedup", "direction": "maximize"}},
}
PRICES = {
    "small": {"model": "Qwen3.8-27B", "currency": "CNY", "unit": "per_1m_tokens", "input_per_1m": 3, "output_per_1m": 12,
              "source": "https://example.test/fixture-price", "retrieved_at": "2026-11-14T08:00:00+00:00"},
    "large": {"model": "gpt-fixture-large", "currency": "USD", "unit": "per_1m_tokens", "input_per_1m": 2, "output_per_1m": 8,
              "source": "https://example.test/fixture-price", "retrieved_at": "2026-11-14T08:00:00+00:00"},
    "decisions": {"model": "gpt-fixture-decisions", "currency": "USD", "unit": "per_1m_tokens", "input_per_1m": 0.1,
                  "output_per_1m": 0.4, "source": "https://example.test/fixture-price", "retrieved_at": "2026-11-14T08:00:00+00:00"},
}


def ledger(requests: int, tin: int | None, tout: int | None) -> dict:
    return {"requests": requests, "latency_s": requests * 4.0, "errors": {}, "input_tokens": tin, "output_tokens": tout,
            "cached_input_tokens": 0, "reasoning_tokens": None,
            "input_tokens_unknown_calls": int(tin is None), "output_tokens_unknown_calls": int(tout is None)}


def main() -> None:
    plan = ra.make_plan(list(TASKS), 1)
    rows = []
    for i, item in enumerate(plan):
        task_id, variant = item["task_id"], item["variant"]
        score = TASKS[task_id]["objective"]["metric"] == "score"
        row = {**item, "mode": "feedback", "task": {"task_id": task_id, **TASKS[task_id]}}
        if task_id.startswith("algotune") and variant == "both_decisions":
            # One planned slot left unexecuted, so not_run stays visible.
            row.update(status="not_run", final_status="not_run")
            rows.append(row)
            continue
        routes = 0 if variant == "baseline" else 4 if variant != "both_decisions" else 7
        large = 0 if variant in ("baseline", "action_decisions") else 3
        small = 10 - large
        by_model = {"small:chat_compat:Qwen3.8-27B": ledger(small, 4000 * small, 500 * small)}
        if large:
            by_model["large:openai_responses:gpt-fixture-large"] = ledger(large, 6000 * large, 900 * large)
        if routes:
            # The action router's token use is unknown on one variant, so cost stays partial there.
            unknown = variant == "action_decisions"
            by_model["router_action:openai_decisions:gpt-fixture-decisions"] = ledger(routes, None if unknown else 300 * routes, 20 * routes)
        value = (17753 + 120 * i) if score else round(1.0 + 0.2 * i, 4)
        final_ok = not (task_id.startswith("ale") and variant == "model_decisions")
        row.update(
            run_id=f"run-fixture-{i + 1}", status="completed",
            best_candidate_id="c2", best_dev={"status": "passed", "correct": 1, "improved": 1,
                                             "speedup": None if score else value,
                                             "objective": {"metric": "score", "value": value, "baseline": 17753} if score else None},
            final_status="completed" if final_ok else "failed",
            final_evaluation={"status": "passed" if final_ok else "wrong_output", "correct": final_ok,
                              "speedup": None if score else value, "objective": {"value": value} if score else None,
                              "normalized": False, "measured": True},
            iterations={"model_requests": small + large + routes, "routing_requests": routes,
                        "generation_requests": small + large, "small_model_requests": small, "large_model_requests": large,
                        "upgrades": 1 if large else 0, "candidates_proposed": 5, "candidates_passed": 4},
            timing={"wall_clock_total_s": 300.0 + 10 * i, "model_wait_s": 250.0, "dev_evaluation_s": 20.0, "final_evaluation_s": 15.0},
            usage=ra._sum_usage(list(by_model.values())), usage_by_model=by_model,
            usage_by_purpose={"routing": ra._sum_usage([v for k, v in by_model.items() if k.startswith("router")]),
                              "generation": ra._sum_usage([v for k, v in by_model.items() if not k.startswith("router")])},
            action_counts={"propose_candidate": 6, "run_validation": 5, "analyze": 2} if routes else {},
            progress=[{"elapsed_s": 30.0, "metric": "score" if score else "speedup", "value": 17753 if score else 1.0,
                       "best_candidate_id": "c0", "usage": {"input_tokens": 4000, "output_tokens": 500}},
                      {"elapsed_s": 200.0, "metric": "score" if score else "speedup", "value": value,
                       "best_candidate_id": "c2", "usage": {"input_tokens": 30000, "output_tokens": 4000}}],
        )
        row["cost"] = ra.costs(by_model, PRICES)
        rows.append(row)
    data = {"comparison_id": "research-routing-fixture", "fixture": True,
            "label": "Fixture only: not an experimental result", "study": "routing", "protocol": "within-task-routing-v2",
            "status": "interrupted", "snapshot_id": "v0", "research_mode": "feedback", "final_evaluation": True,
            "variants": list(ra.VARIANTS), "plan": plan, "plan_sha256": ra._plan_hash(plan), "plan_id": "routing-fixture",
            "price_snapshots": PRICES, "limits": {"max_model_requests": 20, "max_candidates": 10, "wall_clock_s": 900},
            "created_at": "2026-11-14T08:00:00+00:00", "ended_at": None, "runs": rows}
    view = comparison_view(ra.summarize(data))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(rows)} runs, fair={view['fair']}")


if __name__ == "__main__":
    main()
