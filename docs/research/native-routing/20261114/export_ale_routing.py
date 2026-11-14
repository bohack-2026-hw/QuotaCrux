"""Export the frozen routing batch from a consistent local snapshot, without model calls."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "backend/src"))
from routeevo import routing_ablation


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elapsed(start, end):
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def audit_run(root, target, slot, frozen, conn):
    run_id = slot["run_id"]
    source, dest = root / "var/runs" / run_id, target / run_id
    errors = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    def rows(table, order):
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE run_id=? ORDER BY {order}", (run_id,))]

    def copy(path, output, expected=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)
        actual = sha(path)
        check(actual == sha(output), f"copy differs: {path.name}")
        if expected:
            check(actual == expected, f"recorded hash differs: {path.name}")
        return actual

    run = rows("runs", "started_at")[0]
    cfg = json.loads(run["config_json"])
    binding = frozen["tasks"][slot["task_id"]]
    report = read(source / "report.json")
    copy(source / "report.json", dest / "report.json")
    check((run["task_id"], run["mode"], run["snapshot_id"]) == (slot["task_id"], "eval", "v0"), "run identity differs")
    check(cfg["research_protocol"] == {"mode": "feedback", "fixed_model": None, "model_policy": "adaptive", "final_evaluation": True}, "research policy differs")
    for key, value in {"limits": frozen["limits"], "measure": binding["measure"],
                       "environment": binding["environment"], "task_manifest_sha256": binding["manifest_sha256"],
                       "action_schema_sha256": frozen["action_schema_sha256"],
                       "prompt": {"version": frozen["prompt_version"], "system_sha256": frozen["prompt_hashes_by_task"][slot["task_id"]]}}.items():
        check(cfg.get(key) == value, f"frozen configuration differs: {key}")
    check(cfg["router"]["version"] == "off" and not cfg["scripted"], "initial router or scripted provider enabled")
    check(all(cfg["models"][role] == frozen["models"][role] for role in ("small", "large")), "generation configuration differs")
    check(all(cfg["routing"][k] == v for k, v in frozen["routing_manifest"][slot["variant"]].items()), "routing manifest differs")
    check(report["config"] == {k: v for k, v in cfg.items() if k != "environment"}, "report/DB configuration differs")
    check(report["environment"] == cfg["environment"], "report/DB environment differs")
    check(slot["comparison_config"] == routing_ablation.comparable(report), "comparison/report configuration differs")
    check(slot["final_evaluation"] == report["final_evaluation"], "comparison/report final differs")
    check(slot["status"] == report["status"] and slot["final_status"] == report["outcome"]["final_status"], "comparison/report status differs")

    candidates = rows("candidates", "seq")
    calls = rows("model_calls", "started_at, call_id")
    calls.sort(key=lambda c: int(c["call_id"].rsplit("/", 1)[-1][1:]))
    evaluations = rows("evaluations", "started_at, rowid")
    events = rows("events", "event_id")
    for event in events:
        event["payload"] = json.loads(event.pop("payload_json"))
    hashes = {}
    check({p.name for p in (source / "candidates").glob("*.py")} == {f"{c['candidate_id']}.py" for c in candidates}, "candidate inventory differs")
    reported = {c["candidate_id"]: c for c in report["candidates"]}
    for c in candidates:
        name = c["candidate_id"]
        hashes[name] = copy(source / "candidates" / f"{name}.py", dest / "candidates" / f"{name}.py", c["code_sha256"])
        check(reported[name]["code_sha256"] == c["code_sha256"], f"report candidate hash differs: {name}")
    check({p.name for p in (source / "calls").glob("*.json")} == {c["call_id"].rsplit("/", 1)[-1] + ".json" for c in calls}, "call inventory differs")
    for call in calls:
        name = call["call_id"].rsplit("/", 1)[-1] + ".json"
        copy(source / "calls" / name, dest / "model_calls" / name)
        role = "decisions" if call["role"].startswith("router_") else call["role"]
        model = frozen["models"][role]
        check(call["provider"] == model["provider"] and call["model_requested"] == model["model"], f"actual provider/model differs: {name}")
        check(call["model_returned"] in (None, model["model"]), f"returned model differs: {name}")
        check(call["max_output_tokens"] == model["max_output_tokens"] and call["reasoning_effort"] == model["reasoning_effort"], f"actual generation limits differ: {name}")
        if call["role"] == "router_action":
            check(slot["routing"]["action"] == "decisions", "unexpected action routing request")
        if call["role"] == "router_model":
            check(slot["routing"]["model"] == "decisions", "unexpected model routing request")
    generation = [c["role"] for c in calls if c["role"] in ("small", "large")]
    check("small" not in generation[generation.index("large"):] if "large" in generation else True, "generation downgraded after upgrade")
    check(len(calls) == report["iterations"]["model_requests"] == report["usage"]["total"]["requests"], "all-call request count differs")
    for role in ("small", "large"):
        check(sum(c["role"] == role for c in calls) == report["iterations"][f"{role}_model_requests"], f"{role} request count differs")
    check(sum(c["role"].startswith("router_") for c in calls) == report["iterations"]["routing_requests"], "routing request count differs")
    check(len(calls) <= frozen["limits"]["max_model_requests"], "total request budget exceeded")
    check(sum(c["origin"] == "model" for c in candidates) <= frozen["limits"]["max_candidates"], "candidate budget exceeded")
    loops = [e for e in events if e["type"] == "loop_ended"]
    finals = [e for e in events if e["type"] == "final_eval_started"]
    best = run["best_candidate_id"]
    check(len(loops) == 1, "missing/nonunique loop freeze")
    if loops:
        loop = loops[0]
        check(loop["payload"]["best_candidate_id"] == best, "selected candidate changed after freeze")
        check(all(e["event_id"] < loop["event_id"] for e in events if e["type"] in ("model_started", "model_finished", "candidate_created")), "model/candidate event after freeze")
        check(all(c["ended_at"] and c["ended_at"] <= loop["ts"] for c in calls), "request ended after freeze")
        check(all(e["event_id"] > loop["event_id"] and e["payload"]["candidate_id"] == best for e in finals), "final before freeze or wrong candidate")
    manifest = json.loads(conn.execute("SELECT manifest_json FROM tasks WHERE task_id=?", (slot["task_id"],)).fetchone()[0])
    for ev in evaluations:
        detail = json.loads(ev["detail_json"])
        check(ev["dataset_sha256"] == manifest["files"][ev["dataset"] + "_input"]["sha256"], "evaluation dataset hash differs")
        if ev["evaluator_version"] != "static-check":
            check(detail["candidate_sha256"] == hashes[ev["candidate_id"]], "evaluated candidate hash differs")
        if ev["dataset"] == "final":
            # The native evaluator may also measure c0 to report the final baseline.
            check(bool(loops) and ev["started_at"] >= loops[0]["ts"] and ev["candidate_id"] in (best, "c0"), "final evaluated an unfrozen candidate")
    if best:
        copy(source / "candidates" / f"{best}.py", dest / "best.py", hashes[best])
        check(best == slot["best_candidate_id"] == report["best_candidate"]["candidate_id"], "best candidate identity differs")
        if best != "c0":
            selected_dev = [e for e in evaluations if e["candidate_id"] == best and e["dataset"] == "dev"]
            check(bool(selected_dev) and selected_dev[-1]["status"] == "passed" and
                  json.loads(selected_dev[-1]["detail_json"]).get("eligible_for_selection", True), "selected candidate lacks an eligible dev result")
    if report["outcome"]["final_status"] == "completed":
        final = [e for e in evaluations if e["evaluation_id"] == run["final_evaluation_id"]]
        check(len(final) == 1 and bool(finals) and final[0]["candidate_id"] == best, "completed final has no matching frozen evaluation")
        check(report["final_evaluation"]["evaluation_id"] == run["final_evaluation_id"], "report/DB final identity differs")
    audit = {"passed": not errors, "errors": errors, "candidate_sha256": hashes, "model_call_records": calls,
             "loop_freeze_events": loops, "final_start_events": finals, "evaluation_count": len(evaluations)}
    write(dest / "audit.json", audit)
    return report, audit, evaluations


def curves(report, evaluations, calls, prices):
    baseline = next(e for e in evaluations if e["candidate_id"] == "c0" and e["dataset"] == "dev")
    points = [{"elapsed_s": elapsed(report["started_at"], baseline["ended_at"]), "model_requests": 0,
               "tokens": 0, "value": json.loads(baseline["detail_json"])["objective"]["value"]}, *deepcopy(report["progress"])]
    if points:
        points.append({**points[-1], "elapsed_s": report["timing"]["agent_loop_elapsed_s"], "model_requests": len(calls),
                       "tokens": sum(c["input_tokens"] + c["output_tokens"] for c in calls)
                       if all(c["input_tokens"] is not None and c["output_tokens"] is not None for c in calls) else None})
    for p in points:
        costs = {currency: 0 for currency in ("CNY", "USD")}
        prefix = calls[:p["model_requests"]]
        p["tokens"] = (sum(c["input_tokens"] + c["output_tokens"] for c in prefix)
                       if all(c["input_tokens"] is not None and c["output_tokens"] is not None for c in prefix) else None)
        for call in prefix:
            role = "decisions" if call["role"].startswith("router_") else call["role"]
            price = prices[role]; currency = price["currency"]
            if call["input_tokens"] is None or call["output_tokens"] is None:
                costs[currency] = None
            elif costs[currency] is not None:
                costs[currency] += (call["input_tokens"] * price["input_per_1m"] + call["output_tokens"] * price["output_per_1m"]) / 1_000_000
        p["cost"] = costs
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=HERE / "ale-short-freeze.json")
    args = parser.parse_args()
    root, target = args.root.resolve(), args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    frozen = read(root / "execution-freeze.json")
    assert frozen == read(args.freeze), "executed freeze differs from published freeze"
    sources = list((root / "var/comparisons").glob("research-routing-*.json"))
    assert len(sources) == 1, "expected one routing comparison"
    comparison = read(sources[0])
    assert comparison["status"] != "running", "snapshot is still running"
    assert comparison["plan"] == frozen["plan"] and comparison["price_snapshots"] == frozen["price_snapshots"]
    recalculated = routing_ablation.summarize(deepcopy(comparison))
    assert recalculated == comparison, "portable summary differs on recomputation"
    shutil.copyfile(sources[0], target / "comparison.json")
    shutil.copyfile(root / "execution-freeze.json", target / "frozen-manifest.json")
    conn = sqlite3.connect((root / "var/routeevo.sqlite3").as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    records, trajectories, errors = [], [], []
    for slot in comparison["runs"]:
        if not slot.get("run_id"):
            continue
        report, audit, evaluations = audit_run(root, target, slot, frozen, conn)
        records.append({"seq": slot["seq"], "run_id": slot["run_id"], "variant": slot["variant"], "repeat": slot["repeat"],
                        "candidate_files": len(audit["candidate_sha256"]), "calls": len(audit["model_call_records"]), "passed": audit["passed"]})
        errors.extend(f"{slot['seq']}: {e}" for e in audit["errors"])
        trajectories.append({"variant": slot["variant"], "repeat": slot["repeat"], "run_id": slot["run_id"],
                             "points": curves(report, evaluations, audit["model_call_records"], frozen["price_snapshots"])})
    conn.close()
    write(target / "curves.json", trajectories)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = dict(zip(routing_ablation.VARIANTS, ("#2563eb", "#d97706", "#059669", "#9333ea")))
    for key, label in (("elapsed_s", "Episode elapsed seconds"), ("tokens", "Input + output tokens"), ("CNY", "Estimated CNY"), ("USD", "Estimated USD")):
        fig, ax = plt.subplots(figsize=(10, 6))
        for trajectory in trajectories:
            points = trajectory["points"]
            xs = [p["cost"].get(key) if key in ("CNY", "USD") else p.get(key) for p in points]
            ax.step(xs, [p["value"] for p in points], where="post", color=colors[trajectory["variant"]],
                    linestyle=("-", "--", ":")[trajectory["repeat"] - 1], alpha=.85,
                    label=f"{trajectory['variant']} r{trajectory['repeat']}")
        ax.set(xlabel=label, ylabel="Retained development score", title="ahc026 native routing — development trajectory")
        ax.grid(alpha=.2); ax.legend(fontsize=8, ncol=2); fig.tight_layout()
        for suffix in ("svg", "png"):
            fig.savefig(target / f"ahc026-{key}.{suffix}", dpi=150)
        plt.close(fig)
    audit = {"passed": not errors, "errors": errors, "runs": records, "planned": len(comparison["plan"]),
             "status_counts": dict(Counter(r["status"] for r in comparison["runs"])),
             "candidate_files": sum(r["candidate_files"] for r in records), "model_calls": sum(r["calls"] for r in records),
             "export_script_sha256": sha(Path(__file__)), "freeze_sha256": sha(root / "execution-freeze.json")}
    write(target / "audit.json", audit)
    lines = ["# Desktop ahc026 Decisions 路由结果", "", f"执行源码 `{frozen['experiment_sha']}`；计划 `{frozen['plan_id']}`。",
             f"计划四组各{frozen.get('repeats', 3)}次，feedback/adaptive、eval/v0；每轮{frozen['limits']['wall_clock_s']}秒、20个全部HTTP请求、10候选。5 dev / 15 final，dev选优冻结后执行final。探索性小样本，报告实际效应与成本。", "",
             f"运行状态 `{audit['status_counts']}`；审计 `passed={audit['passed']}`，fair=`{comparison['fair']}`。",
             f"导出 {audit['candidate_files']} 份候选、{audit['model_calls']} 份调用JSON；失败和未跑项保留。", "",
             "| 组 | final分数 | small / large请求 | 路由请求 | 升级轮数 | 候选通过/提出 |", "|---|---|---:|---:|---:|---:|"]
    for group in comparison["summary"]["tasks"][0]["variants"]:
        roles = group["generation_roles"]
        lines.append(f"| {group['variant']} | {group['final_values']} | {roles['small']} / {roles['large']} | {group['usage_by_purpose']['routing']['requests']} | {group['upgraded_runs']} / {group['planned']} | {group['candidates_passed']} / {group['candidates_proposed']} |")
    lines += ["", "费用按币种分别记录；unknown/partial不补零。", "", "```json", json.dumps(comparison["cost"]["by_currency"], ensure_ascii=False, indent=2), "```", "",
              "逐轮状态、final、配对差异、交互项、动作频率与routing/generation用量见 [comparison.json](comparison.json)。",
              "过程图使用dev保留分数，不含final；CNY与USD分别为各币种累计成本，不进行换汇相加。预算中路由请求会占用生成机会，未观察到升级的轮次原样保留。"]
    for key in ("elapsed_s", "tokens", "CNY", "USD"):
        lines += ["", f"![ahc026 {key}](ahc026-{key}.svg)"]
    if (root / "user-short-batch-request.json").exists():
        lines.insert(2, "本长预算批次已按用户缩减范围指令停止；原始记录单独保留，不混入360秒短批比较。")
    (target / "README.md").write_text("\n".join(lines) + "\n")
    (target / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(target)}\n" for p in sorted(target.rglob("*")) if p.is_file()))
    print(json.dumps(audit, ensure_ascii=False))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
