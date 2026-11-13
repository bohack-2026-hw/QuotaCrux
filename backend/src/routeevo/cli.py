"""Command-line entry point: `uv run routeevo <command>`."""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
from pathlib import Path

from . import compare, config, db, evaluator, memory, report, taskpkg
from .sandbox import executor


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_tasks_build(args) -> None:
    for t in taskpkg.build_spec(Path(args.spec)):
        files = t.manifest["files"]
        print(f"{t.task_id} [{t.split}] dev {files['dev_input']['bytes'] / 1e6:.1f} MB, final {files['final_input']['bytes'] / 1e6:.1f} MB")


def cmd_tasks_list(args) -> None:
    for r in db.all_rows("SELECT task_id, split, manifest_sha256, manifest_json FROM tasks ORDER BY task_id"):
        m = json.loads(r["manifest_json"])
        p = m["dev_params"]
        print(f"{r['task_id']:<10} {r['split']:<6} rows={p['rows']:<9} keys={p['keys']:<8} order={p['order']:<14} skew={p['skew']:<5} {r['manifest_sha256'][:12]}")


def cmd_tasks_lock(args) -> None:
    _print(taskpkg.write_lock(args.task_ids or None))


def _limits(args) -> config.RunLimits:
    overrides = {k: v for k, v in {
        "max_model_requests": args.max_requests, "max_candidates": args.max_candidates, "wall_clock_s": args.wall_clock,
        "model_request_timeout_s": args.request_timeout,
    }.items() if v is not None}
    return dataclasses.replace(config.RunLimits(), **overrides)


def cmd_run(args) -> None:
    from .agent.runner import RunOptions, Runner

    opts = RunOptions(task_id=args.task_id, mode=args.mode, snapshot_id=args.snapshot, limits=_limits(args),
                      script=Path(args.script).resolve() if args.script else None, label=args.label)
    runner = Runner(opts)
    run_id = runner.create()
    print(f"run {run_id} started (task {args.task_id}, mode {args.mode}, snapshot {runner.snapshot_id})", file=sys.stderr)
    rep = runner.execute()
    _print_summary(rep)


def _print_summary(rep: dict) -> None:
    o, u, t = rep["outcome"], rep["usage"]["total"], rep["timing"]
    lines = [
        f"run            {rep['run_id']}{'  [scripted model: functional check only]' if rep['scripted_model'] else ''}",
        f"status         {rep['status']} / stop: {rep['stop_reason']} ({rep['stop_detail']})",
        f"outcome        {o['summary']}",
        f"flags          ran={o['candidate_ran']} dev_passed={o['dev_validation_passed']} dev_improved={o['dev_improved']} "
        f"final_correct={o['final_correct']} goal_met={o['goal_met']}",
        f"best           {(rep['best_candidate'] or {}).get('candidate_id')}  {(rep['best_candidate'] or {}).get('code_path')}",
        f"iterations     {json.dumps(rep['iterations'])}",
        f"tokens         in={u['input_tokens']} out={u['output_tokens']} reasoning={u['reasoning_tokens']} "
        f"(unknown calls: {u['input_tokens_unknown_calls']})",
        f"cost           {u['cost_usd']} USD [{u['cost_status']}] {u['price_versions']}",
        f"time           total={t['wall_clock_total_s']}s loop={t['agent_loop_s']}s/{t['agent_loop_limit_s']}s "
        f"model={t['model_wait_s']}s eval={t['dev_evaluation_s']}s final={t['final_evaluation_s']}s",
        f"experience     read {len(rep['experience']['read'])} from {rep['experience']['snapshot_read']}"
        f"{'; published ' + rep['experience']['published_snapshot_id'] if rep['experience']['published_snapshot_id'] else ''}",
        f"report         {config.RUNS_DIR / rep['run_id'] / 'report.json'}",
    ]
    print("\n".join(lines))


def cmd_report(args) -> None:
    rep = report.build(args.run_id)
    _print(rep) if args.json else _print_summary(rep)


def cmd_runs(args) -> None:
    sql = "SELECT run_id, task_id, mode, snapshot_id, status, stop_reason, best_candidate_id FROM runs"
    params: tuple = ()
    if args.task:
        sql += " WHERE task_id = ?"
        params = (args.task,)
    for r in db.all_rows(sql + " ORDER BY started_at", params):
        print(f"{r['run_id']}  {r['task_id']:<8} {r['mode']:<5} {r['snapshot_id']:<6} {r['status']:<10} {r['stop_reason'] or '-':<18} best={r['best_candidate_id']}")


def cmd_stop(args) -> None:
    db.update("runs", "run_id", args.run_id, {"stop_requested": 1})
    print(f"stop requested for {args.run_id}; it ends after the current step")


def cmd_check(args) -> None:
    task = taskpkg.load(args.task_id)
    ev = evaluator.evaluate(task, Path(args.code).read_bytes(), args.dataset, config.MeasureConfig(), config.RunLimits(),
                            measure_timing=not args.no_timing)
    _print({**ev.public_feedback(), "detail": {k: v for k, v in ev.detail.items() if k != "samples"}})


def cmd_calibrate(args) -> None:
    """Time the initial program on a task's dev data and the fixed container/pipe overhead."""
    task = taskpkg.load(args.task_id)
    m, lim = config.MeasureConfig(), config.RunLimits()
    data = task.dataset("dev")[0].read_bytes()
    code = task.initial_code.encode()
    drain = b"import sys\nsys.stdin.buffer.read()\n"
    base, over = [], []
    for _ in range(args.repeats):
        r = executor.run_sample(code, data, lim.measurement_timeout_s, m)
        base.append(r.elapsed_s if r.status == "ok" else float("nan"))
        r = executor.run_sample(drain, data, lim.measurement_timeout_s, m)
        over.append(r.elapsed_s if r.status == "ok" else float("nan"))
    _print({"task_id": task.task_id, "input_mb": round(len(data) / 1e6, 2),
            "baseline_s": [round(x, 4) for x in base], "baseline_median_s": round(statistics.median(base), 4),
            "read_input_only_s": [round(x, 4) for x in over], "read_input_only_median_s": round(statistics.median(over), 4),
            "fixed_overhead_share": round(statistics.median(over) / statistics.median(base), 3)})


def cmd_snap_list(args) -> None:
    active = memory.active_snapshot()
    for r in db.all_rows("SELECT * FROM snapshots ORDER BY version"):
        n = len(memory.snapshot_experience_ids(r["snapshot_id"]))
        mark = "*" if r["snapshot_id"] == active else " "
        print(f"{mark} {r['snapshot_id']:<5} parent={r['parent_snapshot_id'] or '-':<5} experiences={n:<4} from={r['source_run_id'] or '-'}  {r['created_at']}")
    for h in db.all_rows("SELECT * FROM pointer_history ORDER BY id DESC LIMIT 5"):
        print(f"  pointer {h['from_snapshot_id']} -> {h['to_snapshot_id']} by {h['actor']} at {h['ts']}: {h['reason']}")


def cmd_snap_show(args) -> None:
    snap = memory.snapshot(args.snapshot_id)
    if not args.full:
        for e in snap["experiences"]:
            e["action"].pop("diff_vs_initial", None)
    _print(snap)


def cmd_snap_diff(args) -> None:
    _print(memory.compare_snapshots(args.a, args.b))


def cmd_snap_activate(args) -> None:
    _print(memory.activate(args.snapshot_id, reason=args.reason or "manual switch", actor="cli"))


def cmd_experience(args) -> None:
    _print(memory.experience(args.experience_id))


def cmd_compare(args) -> None:
    script = str(Path(args.script).resolve()) if args.script else None
    cid = compare.create(args.task_ids, args.a, args.b, args.repeats, args.label, script)
    print(f"comparison {cid}: {len(args.task_ids)} tasks x 2 snapshots x {args.repeats} repeats, serial", file=sys.stderr)
    _print_comparison(compare.execute(cid))


def _print_comparison(s: dict) -> None:
    print(f"comparison {s['comparison_id']} [{s['status']}] {s['finished_runs']}/{s['planned_runs']} runs, fair={s['fair']}"
          f"{'  [scripted model: functional check only]' if s['scripted_model'] else ''}")
    cols = ("runs", "goal_met", "success_rate", "final_speedup_median", "no_improvement_runs", "model_requests_median",
            "upgrades_total", "cost_usd_total", "wall_clock_s_total", "agent_loop_s_median")
    for snap, side in s["sides"].items():
        print(f"  {snap:<5} " + "  ".join(f"{c}={side[c]}" for c in cols)
              + f"  out_tokens={side['output_tokens']['total']} in_tokens={side['input_tokens']['total']}")
    lc = s["learning_cost"]
    print(f"  learning cost {s['snapshot_a']}->{s['snapshot_b']}: {lc.get('cost_usd')} USD {lc.get('cost_status')} "
          f"out_tokens={lc.get('output_tokens')} time={lc.get('wall_clock_s')}s" if lc["in_lineage"] else f"  {lc['note']}")
    for e in s["errors"]:
        print(f"  error #{e['seq']} {e['task_id']} {e['snapshot_id']}: {e['error']}")
    print(f"  full summary: {config.VAR_DIR / 'comparisons' / (s['comparison_id'] + '.json')}")


def cmd_comparison(args) -> None:
    s = compare.summarize(args.comparison_id)
    _print(s) if args.json else _print_comparison(s)


def cmd_probe(args) -> None:
    """Send exactly the first request a run would send to one model role; print latency, usage and cost."""
    from .agent import actions, prompt
    from .agent.runner import _make_clients, RunOptions
    from .llm.pricing import estimate_cost

    task = taskpkg.load(args.task_id)
    clients, cfgs = _make_clients(RunOptions(task_id=args.task_id))
    cfg = cfgs[args.role]
    state = prompt.build_state(
        task=task, candidates=[{"candidate_id": "c0", "origin": "initial", "parent_candidate_id": None, "code": task.initial_code,
                                "latest_evaluation": {"status": "passed", "correct": True, "speedup": 1.0}}],
        evidence=[], history=[], experiences=None, snapshot_id="v0",
        budget={"model_requests_used": 0, "model_requests_max": config.RunLimits().max_model_requests, "probe": True},
        last_feedback=None)
    print(f"probing {args.role}: {cfg.provider} {cfg.model} effort={cfg.reasoning_effort} max_output={cfg.max_output_tokens}"
          f" timeout={args.timeout}s", file=sys.stderr)
    res = clients[args.role].complete(prompt.SYSTEM_PROMPT, state, actions.ACTION_SCHEMA, args.timeout, cfg.max_output_tokens)
    cost, cost_status, version = estimate_cost(cfg.provider, cfg.model, res.usage, res.error_kind != "config")
    try:
        parsed = actions.parse(res.text or "").action if res.ok else None
    except actions.InvalidAction as exc:
        parsed = f"invalid: {exc.kind}"
    _print({"ok": res.ok, "error_kind": res.error_kind, "error_message": res.error_message, "latency_s": round(res.latency_s, 2),
            "model_returned": res.model_returned, "request_id": res.request_id, "parsed_action": parsed,
            "usage": {k: getattr(res.usage, k) for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "source")},
            "cost_usd": cost, "cost_status": cost_status, "price_version": version,
            "within_request_timeout": res.latency_s <= config.RunLimits().model_request_timeout_s})


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("routeevo.api:app", host=args.host, port=args.port, log_level="info")


def main(argv: list[str] | None = None) -> None:
    config.load_dotenv()
    p = argparse.ArgumentParser(prog="routeevo")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tasks", help="build, list and pin task packages")
    tsub = t.add_subparsers(dest="tcmd", required=True)
    b = tsub.add_parser("build")
    b.add_argument("--spec", default=str(config.TASK_SPEC_DIR / "spec.json"))
    b.set_defaults(fn=cmd_tasks_build)
    tsub.add_parser("list").set_defaults(fn=cmd_tasks_list)
    lk = tsub.add_parser("lock", help="pin manifests in tasks/lock.json")
    lk.add_argument("task_ids", nargs="*")
    lk.set_defaults(fn=cmd_tasks_lock)

    r = sub.add_parser("run", help="run the agent on one task")
    r.add_argument("task_id")
    r.add_argument("--mode", choices=["learn", "eval"], default="eval")
    r.add_argument("--snapshot", help="experience snapshot id (default: active)")
    r.add_argument("--script", help="scripted model JSON (functional checks only)")
    r.add_argument("--label")
    r.add_argument("--max-requests", type=int)
    r.add_argument("--max-candidates", type=int)
    r.add_argument("--wall-clock", type=float)
    r.add_argument("--request-timeout", type=float)
    r.set_defaults(fn=cmd_run)

    rp = sub.add_parser("report")
    rp.add_argument("run_id")
    rp.add_argument("--json", action="store_true")
    rp.set_defaults(fn=cmd_report)

    rs = sub.add_parser("runs")
    rs.add_argument("--task")
    rs.set_defaults(fn=cmd_runs)

    st = sub.add_parser("stop")
    st.add_argument("run_id")
    st.set_defaults(fn=cmd_stop)

    c = sub.add_parser("check", help="evaluate a program file outside any run")
    c.add_argument("task_id")
    c.add_argument("code")
    c.add_argument("--dataset", choices=["dev", "final"], default="dev")
    c.add_argument("--no-timing", action="store_true")
    c.set_defaults(fn=cmd_check)

    cal = sub.add_parser("calibrate", help="time the initial program and fixed overhead on dev data")
    cal.add_argument("task_id")
    cal.add_argument("--repeats", type=int, default=5)
    cal.set_defaults(fn=cmd_calibrate)

    sn = sub.add_parser("snapshots", help="experience snapshots, diffs and rollback")
    snsub = sn.add_subparsers(dest="scmd", required=True)
    snsub.add_parser("list").set_defaults(fn=cmd_snap_list)
    ss = snsub.add_parser("show")
    ss.add_argument("snapshot_id")
    ss.add_argument("--full", action="store_true", help="include code diffs")
    ss.set_defaults(fn=cmd_snap_show)
    sd = snsub.add_parser("diff")
    sd.add_argument("a")
    sd.add_argument("b")
    sd.set_defaults(fn=cmd_snap_diff)
    sa = snsub.add_parser("activate", help="switch the snapshot future runs read (rollback)")
    sa.add_argument("snapshot_id")
    sa.add_argument("--reason")
    sa.set_defaults(fn=cmd_snap_activate)

    ex = sub.add_parser("experience")
    ex.add_argument("experience_id")
    ex.set_defaults(fn=cmd_experience)

    cp = sub.add_parser("compare", help="frozen old-vs-new snapshot comparison on held-out tasks")
    cp.add_argument("task_ids", nargs="+")
    cp.add_argument("--a", required=True, help="old snapshot (e.g. v0)")
    cp.add_argument("--b", required=True, help="new snapshot")
    cp.add_argument("--repeats", type=int, default=3)
    cp.add_argument("--label")
    cp.add_argument("--script", help="scripted model JSON (functional checks only)")
    cp.set_defaults(fn=cmd_compare)
    cs = sub.add_parser("comparison")
    cs.add_argument("comparison_id")
    cs.add_argument("--json", action="store_true")
    cs.set_defaults(fn=cmd_comparison)

    pr = sub.add_parser("probe", help="send one real first-step request to a model role")
    pr.add_argument("role", choices=["small", "large"])
    pr.add_argument("--task-id", default="A-01")
    pr.add_argument("--timeout", type=float, default=300.0)
    pr.set_defaults(fn=cmd_probe)

    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
