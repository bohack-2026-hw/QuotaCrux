"""Write docs/archive/memory-learning-results.md from stored records: learning runs, comparisons, per-task outcomes, costs.

Three configurations are reported. Version 3 (current) adds the router, online memory and two new task families; it is
measured on the sealed S stream (memory vs fresh). Version 2 re-validates verified programs from experience before
asking a model: A learning in two rounds, B development comparison, D sealed held-out. Version 1 (text experience only)
keeps its A learning, B and C results unchanged.

    uv run python scripts/write_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

from quotacrux import compare, config, db, memory, narrative, report, research

OUT = Path(__file__).resolve().parents[2] / "docs" / "archive" / "memory-learning-results.md"


def x(v) -> str:
    return "—" if v is None else f"{v:.2f}×"


def usd(v) -> str:
    return "未知" if v is None else f"${v:.3f}"


def n(v) -> str:
    return "—" if v is None else f"{v:,}"


def g(v) -> str:
    return "—" if v is None else f"{v:g}"


def upgrade_rule(cid: str) -> str:
    rows = db.all_rows("SELECT DISTINCT json_extract(r.config_json, '$.upgrade_rule.id') AS u FROM comparison_runs cr"
                       " JOIN runs r ON r.run_id = cr.run_id WHERE cr.comparison_id = ?", (cid,))
    return ", ".join(r["u"] or "?" for r in rows)


V1_LEARN = ["formal A learning"]
V2_LEARN = ["reuse A learning r1", "reuse A learning r2"]
# label prefix -> key; the first matching prefix wins, newest comparison per key
LABELS = [("S online stream", "S"), ("B dev comparison · reuse", "B2"), ("D final held-out · reuse", "D"), ("B dev", "B"),
          ("C final", "C")]
FAMILY_ZH = {"groupagg": "分组聚合", "logstats": "访问日志", "intervals": "区间合并"}
ROUTE_MARK = {"reuse": "↺", "familiar": "○", "new_family": "★", "new_conditions": "◆", "router_off": "·", "no_model_request": "–"}


def comparisons() -> dict[str, dict]:
    out = {}
    for r in db.all_rows("SELECT comparison_id, label FROM comparisons WHERE status != 'running' ORDER BY created_at"):
        label = r["label"] or ""
        key = next((k for prefix, k in LABELS if label.startswith(prefix)), None)
        if key:
            out[key] = compare.summarize(r["comparison_id"])
    return out


def learn_runs(labels: list[str]) -> list[str]:
    q = ",".join("?" * len(labels))
    return [r["run_id"] for r in db.all_rows(f"SELECT run_id FROM runs WHERE mode = 'learn' AND status != 'running' AND json_extract(config_json, '$.label') IN ({q})"
                                             " ORDER BY started_at", labels)]


def section_learning_v2(lines: list[str]) -> None:
    lines += ["### 3.1 学习：A 批两轮，从 v0 开始", "",
              "第 1 轮从空经验 v0 开始串行学习 A-01—A-06；第 2 轮在第 1 轮的最终快照上把同样 6 个任务再学一遍。每次学习运行先由程序复验"
              "快照中条件最接近的已验证程序（不调用模型）；若已达标，本次目标提高到超过其中最佳 5%，模型的请求只用于超越已知最佳。", "",
              "| 轮次 | 任务 | 读取快照 | 复验程序（改善） | 本次目标 | 结果 | 最终加速比 | 模型请求 | 升级 | 费用 | 耗时 | 发布 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    rounds: dict[str, dict] = {}
    for label in V2_LEARN:
        ids = learn_runs([label])
        if not ids:
            continue
        rnd = "第 " + label[-1] + " 轮"
        agg = rounds.setdefault(rnd, {"cost": 0.0, "requests": 0, "time": 0.0, "speedups": {}, "goal": 0, "runs": 0})
        for rid in ids:
            r = report.build(rid)
            u, it = r["usage"]["total"], r["iterations"]
            agg["cost"] += u["cost_usd"] or 0
            agg["requests"] += it["model_requests"]
            agg["time"] += r["timing"]["wall_clock_total_s"] or 0
            agg["runs"] += 1
            agg["goal"] += r["outcome"]["goal_met"]
            agg["speedups"][r["task"]["task_id"]] = r["outcome"]["final_speedup"]
            lines.append(f"| {rnd} | {r['task']['task_id']} | {r['snapshot_id']} | {it['programs_reused']}（{it['programs_reused_improved']}） | "
                         f"{r['run_target_speedup']:g}× | {r['outcome']['summary']} | {x(r['outcome']['final_speedup'])} | {it['model_requests']} | "
                         f"{it['upgrades']} | {usd(u['cost_usd'])} | {r['timing']['wall_clock_total_s']:.0f}s | {r['experience']['published_snapshot_id'] or '—'} |")
    lines += ["", "| 轮次 | 达标 | 模型请求 | 费用 | 耗时 | 各任务最终加速比 |", "|---|---|---|---|---|---|"]
    for rnd, a in rounds.items():
        sp = " ".join(f"{t} {x(v)}" for t, v in a["speedups"].items())
        lines.append(f"| {rnd} | {a['goal']}/{a['runs']} | {a['requests']} | {usd(a['cost'])} | {a['time']:.0f}s | {sp} |")
    ids = learn_runs(V2_LEARN)
    final = next((report.build(i)["experience"]["published_snapshot_id"] for i in reversed(ids)
                  if report.build(i)["experience"]["published_snapshot_id"]), None)
    if final:
        snap = memory.snapshot(final)
        programs = {memory.normalized_code(e["action"]["code"]) for e in snap["experiences"] if e["outcome"] == "success" and e["action"].get("code")}
        lines += ["", f"最终快照 **{final}** 含 {len(snap['experiences'])} 条经验（成功 {snap['counts'].get('success', 0)}、"
                      f"无收益 {snap['counts'].get('no_gain', 0)}、失败 {snap['counts'].get('failure', 0)}），其中可复验的不同程序 {len(programs)} 个。", ""]


def section_learning(lines: list[str]) -> None:
    reps = [report.build(r) for r in learn_runs(V1_LEARN)]
    lines += ["### 4.1 学习阶段（A 批，串行，从 v0 开始）", "",
              "| 任务 | 读取快照 | 读到经验 | 结果 | 最终加速比 | 模型请求 | 升级 | 费用 | 耗时 | 发布 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    total = 0.0
    for r in reps:
        u = r["usage"]["total"]
        total += u["cost_usd"] or 0
        lines.append(f"| {r['task']['task_id']} | {r['snapshot_id']} | {len(r['experience']['read'])} | {r['outcome']['summary']} | "
                     f"{x(r['outcome']['final_speedup'])} | {r['iterations']['model_requests']} | {r['iterations']['upgrades']} | "
                     f"{usd(u['cost_usd'])} | {r['timing']['wall_clock_total_s']:.0f}s | {r['experience']['published_snapshot_id'] or '—'} |")
    final = next((r["experience"]["published_snapshot_id"] for r in reversed(reps) if r["experience"]["published_snapshot_id"]), "v0")
    snap = memory.snapshot(final)
    lines += ["", f"学习总费用 {usd(total)}。最终快照 **{final}** 含 {len(snap['experiences'])} 条经验："
              f"成功 {snap['counts'].get('success', 0)}、无收益 {snap['counts'].get('no_gain', 0)}、失败 {snap['counts'].get('failure', 0)}。",
              "学习过程中“读到相关经验后第一次请求就达标”的现象只是观察，不作为效果证据；效果以下面的留出对照为准。", ""]


TITLES = {"B2": "3.2 B 批开发对照", "D": "3.3 D 批封存留出（第二版最终验收）", "B": "4.2 B 批开发对照", "C": "4.3 C 批最终留出"}


def section_comparison(lines: list[str], key: str, c: dict) -> None:
    a, b = c["snapshot_a"], c["snapshot_b"]
    A, B = c["sides"][a], c["sides"][b]
    lines += [f"### {TITLES[key]}：{a} vs {b}", "",
              f"`{c['comparison_id']}` · {len(c['tasks'])} 个任务 × 2 个快照 × {c['repeats']} 次 · 完成 {c['finished_runs']}/{c['planned_runs']} · "
              f"配置指纹{'一致' if c['fair'] else '**不一致**'}（{', '.join(c['config_fingerprints'])}） · 升级规则 {upgrade_rule(c['comparison_id'])}", "",
              f"| 指标 | {a}（{'无经验' if a == 'v0' else '旧经验'}） | {b}（新经验） |", "|---|---|---|",
              f"| 达标 / 运行 | {A['goal_met']} / {A['runs']} | {B['goal_met']} / {B['runs']} |",
              f"| 最终加速比中位数（有计时结果的运行） | {x(A['final_speedup_median'])} | {x(B['final_speedup_median'])} |",
              f"| 无改进运行（保留初始程序） | {A['no_improvement_runs']} | {B['no_improvement_runs']} |",
              f"| 模型请求中位数 / 合计 | {g(A['model_requests_median'])} / {A.get('model_requests_total', '—')} | {g(B['model_requests_median'])} / {B.get('model_requests_total', '—')} |",
              *([f"| 复用经验中的程序直接达标 / 未调用模型的运行 | {A.get('goal_met_from_reuse', 0)} / {A.get('runs_without_model_request', 0)} | "
                 f"{B.get('goal_met_from_reuse', 0)} / {B.get('runs_without_model_request', 0)} |"] if key in ("B2", "D") else []),
              f"| 升级到 GPT 次数 | {A['upgrades_total']} | {B['upgrades_total']} |",
              f"| 失败候选合计 | {A['candidates_failed_total']} | {B['candidates_failed_total']} |",
              f"| 输入 / 输出 Token 合计 | {n(A['input_tokens']['total'])} / {n(A['output_tokens']['total'])} | {n(B['input_tokens']['total'])} / {n(B['output_tokens']['total'])} |",
              f"| 模型费用合计（GPT 估算） | {usd(A['cost_usd_total'])} | {usd(B['cost_usd_total'])} |",
              f"| 总耗时 / 循环时长中位数 | {A['wall_clock_s_total']:.0f}s / {A['agent_loop_s_median']:.0f}s | {B['wall_clock_s_total']:.0f}s / {B['agent_loop_s_median']:.0f}s |",
              f"| 终止原因 | {json.dumps(A['stop_reasons'], ensure_ascii=False)} | {json.dumps(B['stop_reasons'], ensure_ascii=False)} |",
              "", "逐任务（每格为 3 次运行的最终加速比；`✕` 表示未达标，`—` 表示没有计时结果）：", "",
              f"| 任务 | {a} | {b} | {a} 请求 | {b} 请求 |", "|---|---|---|---|---|"]
    for t in c["tasks"]:
        cells, reqs = [], []
        for s in (a, b):
            runs = c["per_task"][t][s]["runs"]
            cells.append(" ".join(f"{x(r['final_speedup'])}{'' if r['goal_met'] else '✕'}" for r in runs))
            reqs.append(" ".join(str(r["model_requests"]) for r in runs))
        lines.append(f"| {t} | {cells[0]} | {cells[1]} | {reqs[0]} | {reqs[1]} |")
    lc = c["learning_cost"]
    if lc.get("in_lineage"):
        lines += ["", f"学习成本（{a} → {b} 的 {len(lc['learn_runs'])} 次学习运行）：{usd(lc['cost_usd'])}，"
                      f"输出 Token {n(lc['output_tokens'])}，耗时 {lc['wall_clock_s']:.0f}s。"]
    observations(lines, c)
    if c["errors"]:
        lines += ["", f"出错的计划运行：{len(c['errors'])} 次，例如 {c['errors'][0]['error']}"]
    note = narrative.evolution_note(c["comparison_id"])
    lines += ["", "经验带来的变化（由对照数据自动填写）：", ""] + [f"{i}. {line}" for i, line in enumerate(note["lines"], 1)] + [""]


def observations(lines: list[str], c: dict) -> None:
    """Facts computed from the per-task table that the headline medians hide."""
    a, b = c["snapshot_a"], c["snapshot_b"]
    lower, higher, missed = [], [], []
    for t in c["tasks"]:
        med = {}
        for s in (a, b):
            sp = sorted(r["final_speedup"] for r in c["per_task"][t][s]["runs"] if r["final_speedup"] is not None)
            med[s] = sp[len(sp) // 2] if sp else None
            missed += [f"{t}/{s}（{x(r['final_speedup'])}）" for r in c["per_task"][t][s]["runs"]
                       if r["stop_reason"] == "goal_reached" and not r["goal_met"]]
        if med[a] is not None and med[b] is not None:
            (lower if med[b] < med[a] - 0.05 else higher if med[b] > med[a] + 0.05 else []).append(t)
    A, B = c["sides"][a], c["sides"][b]
    lines += ["", "观察（由上表计算）：", "",
              f"- 每任务加速比中位数：{b} 明显更低的任务 {', '.join(lower) or '无'}；明显更高的任务 {', '.join(higher) or '无'}（相差超过 0.05×）。"
              f"达标线是 1.10×，评测运行达到目标即停止。"]
    wins = sum(1 for t in c["tasks"] for r in c["per_task"][t][b]["runs"] if r.get("best_from_reuse") and r["goal_met"])
    if wins:
        loops = sorted(r["agent_loop_s"] for t in c["tasks"] for r in c["per_task"][t][b]["runs"] if r.get("best_from_reuse") and r["agent_loop_s"])
        lines.append(f"- {b} 有 {wins} 次运行由复用的程序直接达标，这些运行的循环时长中位数 {loops[len(loops) // 2]:.0f}s。")
        lines.append("- 最终交付的复用程序来自哪次学习（任务 / 候选，原实测加速比）：" + "；".join(
            f"{t} ← " + "、".join(sorted(set(reuse_source(r["run_id"]) for r in c["per_task"][t][b]["runs"] if r.get("best_from_reuse"))))
            for t in c["tasks"] if any(r.get("best_from_reuse") for r in c["per_task"][t][b]["runs"])) + "。")
    if missed:
        lines.append(f"- 开发数据上已达标、但最终测试未满足“全部样本快于基线”的运行 {len(missed)} 次：{'、'.join(missed)}；按规则记为未达标。")
    per = {t: sum(r["cost_usd"] or 0 for r in c["per_task"][t][b]["runs"]) for t in c["tasks"]}
    tot = sum(per.values())
    if tot:
        top = max(per, key=per.get)
        if per[top] / tot >= 0.5:
            lines.append(f"- {b} 的 GPT 费用 {usd(tot)} 中有 {usd(per[top])}（{per[top] / tot:.0%}）来自 {top}，其余 {len(per) - 1} 个任务合计 {usd(tot - per[top])}。")
    ia, ib = A["input_tokens"]["total"], B["input_tokens"]["total"]
    if ia and ib and ib > ia:
        lines.append(f"- 输入 Token {n(ia)} → {n(ib)}：经验摘要进入提示词，单次请求更长；请求次数和输出 Token 减少，GPT 费用仍以实测为准。")


def reuse_source(run_id: str) -> str:
    rep = report.build(run_id)
    best = rep["best_candidate"]["candidate_id"]
    st = next(x for x in rep["steps"] if x["action"] == "reuse_candidate" and x["candidate_id"] == best)
    e = memory.experience(st["params"]["experience_id"])
    return f"{e['conditions']['task_id']} {e['source']['candidate_id']}（{x(e['result']['speedup'])}）"


def section_tuning(lines: list[str]) -> None:
    ids = [r["run_id"] for r in db.all_rows("SELECT run_id FROM runs WHERE json_extract(config_json, '$.label') = 'dev T router'"
                                            " AND status != 'running' ORDER BY started_at")]
    if not ids:
        return
    lines += ["### 2.1 调优：T 批（新任务族，在线模式，从 v19 依次写入）", "",
              "T 批的条件与 S 批的“首次出现”和“新条件”任务对应，只用于检查新任务族和分流器能否工作；S 批在任何第三版运行之前封存。", "",
              "| 任务 | 任务族 · 输入规模和特点 | 读取 → 发布 | 路线 | 模型请求 | 费用 | 最终加速比 | 循环时长 |", "|---|---|---|---|---|---|---|---|"]
    for i in ids:
        r = report.build(i)
        route = (r["route"] or {}).get("reason") or ("reuse" if r["outcome"].get("best_from_reuse") else "—")
        lines.append(f"| {r['task']['task_id']} | {r['task']['workload']} | {r['snapshot_id']} → {r['experience']['published_snapshot_id'] or '—'} | "
                     f"{narrative.ROUTE_ZH.get(route, route)} | {r['iterations']['model_requests']} | {usd(r['usage']['total']['cost_usd'])} | "
                     f"{x(r['outcome']['final_speedup'])}{'' if r['outcome']['goal_met'] else '（未达标）'} | {r['timing']['agent_loop_s']:.0f}s |")
    lines.append("")


def _side_rows(F: dict, M: dict) -> list[str]:
    def routes(s):
        return "，".join(f"{narrative.ROUTE_ZH.get(k, k)} {v}" for k, v in sorted(s["routes"].items(), key=lambda kv: -kv[1]))
    return [
        f"| 达标 / 运行 | {F['goal_met']}/{F['runs']} | {M['goal_met']}/{M['runs']} |",
        f"| 最终加速比中位数 | {x(F['final_speedup_median'])} | {x(M['final_speedup_median'])} |",
        f"| 大模型（GPT）请求合计 | {F['large_model_requests_total']} | {M['large_model_requests_total']} |",
        f"| 用到大模型的运行 | {F['runs_using_large_model']} | {M['runs_using_large_model']} |",
        f"| 没有调用任何模型的运行 | {F['runs_without_model_request']} | {M['runs_without_model_request']} |",
        f"| 模型费用（估算） | {usd(F['cost_usd_total'])} | {usd(M['cost_usd_total'])} |",
        f"| 输入 / 输出 Token | {n(F['input_tokens']['total'])} / {n(F['output_tokens']['total'])} | {n(M['input_tokens']['total'])} / {n(M['output_tokens']['total'])} |",
        f"| 单次研究循环时长中位数 | {F['agent_loop_s_median']:.1f}s | {M['agent_loop_s_median']:.1f}s |",
        f"| 总耗时 | {F['wall_clock_s_total']:.0f}s | {M['wall_clock_s_total']:.0f}s |",
        f"| 分流 | {routes(F)} | {routes(M)} |",
    ]


def section_stream(lines: list[str], s: dict) -> None:
    F, M = s["sides"]["fresh"], s["sides"]["memory"]
    fams = sorted({p["family"] for p in s["positions"]})
    lines += ["### 2.2 S 任务流：带记忆 vs 不带记忆（封存，配置冻结后运行一次）", "",
              f"从 {s['start_snapshot']} 出发（只有分组聚合的经验），{len(s['tasks'])} 个任务按固定顺序出现，混合 {len(fams)} 个任务族。"
              f"带记忆一侧用在线模式：交付后把验证过的结果写入经验，下一个任务读取；不带记忆一侧每个任务都只读 {s['start_snapshot']}。"
              f"两侧按任务交替先后、串行运行。每次重放都从 {s['start_snapshot']} 重新学起，共 {s['repeats']} 次，所以重复的是学习过程本身。"
              f"配置指纹一致：{'是' if s['fair'] else '否'}（`{'`, `'.join(s['config_fingerprints'])}`）。"
              + ("" if not s["errors"] else f" 计划运行出错 {len(s['errors'])} 次。"), "",
              "| 指标 | 不带记忆 | 带记忆 |", "|---|---|---|", *_side_rows(F, M), ""]
    f1, fl = s["first_of_family"], s["repeats_of_family"]
    lines += [f"按任务在流中的位置拆开：新任务族（起点 {s['start_snapshot']} 没有它的经验）在流中第一次出现时，两侧都没有该族经验，条件相同；"
              "其余任务才体现记忆的作用。", "",
              "| | 新任务族首次出现（不带 → 带记忆） | 其余任务（不带 → 带记忆） |", "|---|---|---|",
              f"| 运行 | {f1['fresh']['runs']} → {f1['memory']['runs']} | {fl['fresh']['runs']} → {fl['memory']['runs']} |",
              f"| 达标 | {f1['fresh']['goal_met']} → {f1['memory']['goal_met']} | {fl['fresh']['goal_met']} → {fl['memory']['goal_met']} |",
              f"| 大模型请求 | {f1['fresh']['large_model_requests_total']} → {f1['memory']['large_model_requests_total']} | "
              f"{fl['fresh']['large_model_requests_total']} → {fl['memory']['large_model_requests_total']} |",
              f"| 没有调用模型 | {f1['fresh']['runs_without_model_request']} → {f1['memory']['runs_without_model_request']} | "
              f"{fl['fresh']['runs_without_model_request']} → {fl['memory']['runs_without_model_request']} |",
              f"| 费用 | {usd(f1['fresh']['cost_usd_total'])} → {usd(f1['memory']['cost_usd_total'])} | {usd(fl['fresh']['cost_usd_total'])} → {usd(fl['memory']['cost_usd_total'])} |",
              f"| 循环时长中位数 | {f1['fresh']['agent_loop_s_median']:.1f}s → {f1['memory']['agent_loop_s_median']:.1f}s | "
              f"{fl['fresh']['agent_loop_s_median']:.1f}s → {fl['memory']['agent_loop_s_median']:.1f}s |",
              f"| 最终加速比中位数 | {x(f1['fresh']['final_speedup_median'])} → {x(f1['memory']['final_speedup_median'])} | "
              f"{x(fl['fresh']['final_speedup_median'])} → {x(fl['memory']['final_speedup_median'])} |", ""]
    lines += ["| 任务族 | 运行 | 达标（不带 → 带） | 大模型请求 | 费用 | 最终加速比中位数 | 循环时长中位数 |", "|---|---|---|---|---|---|---|"]
    for fam, d in s["by_family"].items():
        a, b = d["fresh"], d["memory"]
        lines.append(f"| {FAMILY_ZH.get(fam, fam)} | {a['runs']} + {b['runs']} | {a['goal_met']} → {b['goal_met']} | "
                     f"{a['large_model_requests_total']} → {b['large_model_requests_total']} | {usd(a['cost_usd_total'])} → {usd(b['cost_usd_total'])} | "
                     f"{x(a['final_speedup_median'])} → {x(b['final_speedup_median'])} | {a['agent_loop_s_median']:.1f}s → {b['agent_loop_s_median']:.1f}s |")
    lines += ["", "逐任务（每格三个符号是三次重放的路线：↺ 复用直接交付，★ 全新任务族 → 大模型，◆ 新条件 → 大模型，○ 相近经验 → 小模型；"
              "随后是最终加速比，未达标标“!”）：", "",
              "| # | 任务 | 输入规模和特点 | 带记忆 | 不带记忆 |", "|---|---|---|---|---|"]

    def cell(runs):
        return " ".join(ROUTE_MARK.get(r["route"], "?") for r in runs) + " · " + " ".join(
            f"{x(r['final_speedup'])}{'' if r['goal_met'] else '!'}" for r in runs)
    for p in s["positions"]:
        lines.append(f"| {p['position']} | {p['task_id']}{'（新任务族首次）' if p['first_of_family'] else ''} | {p['workload']} | "
                     f"{cell(p['arms']['memory'])} | {cell(p['arms']['fresh'])} |")
    lines += ["", "| 重放 | 带记忆一侧的版本链 | 新发布版本 | 经验条数 |", "|---|---|---|---|"]
    for gr in s["growth"]:
        lines.append(f"| 第 {gr['repeat']} 次 | {gr['start']} → {gr['end']} | {gr['published_versions']} | {gr['experiences_start']} → {gr['experiences_end']} |")
    stopped = [r for r in db.all_rows("SELECT comparison_id, created_at FROM comparisons WHERE label LIKE 'S online stream%' AND status = 'stopped'"
                                      " ORDER BY created_at")]
    for r in stopped:
        st = compare.summarize(r["comparison_id"])
        ev = db.one("SELECT payload_json FROM events WHERE run_id = ? AND type = 'stream_stopped_by_operator'", (r["comparison_id"],))
        api = sum(1 for p in st["positions"] for a in ("memory", "fresh") for x_ in p["arms"][a] if x_["stop_reason"] == "model_api_error")
        F0, M0 = st["sides"]["fresh"], st["sides"]["memory"]
        lines += ["", f"**中止的第一次运行**（`{r['comparison_id']}`，记录全部保留）：运行到 {st['finished_runs']}/{st['planned_runs']} 时人工停止。"
                  "原因：03:32 UTC 起 OpenAI 接口连续出现网络错误（SSL EOF、服务器断开），"
                  f"不带记忆一侧有 {api} 次运行因此以 model_api_error 结束；继续运行只会测到网络故障。停止前的结果方向与重跑一致："
                  f"大模型请求 {F0['large_model_requests_total']} → {M0['large_model_requests_total']}，费用 {usd(F0['cost_usd_total'])} → {usd(M0['cost_usd_total'])}，"
                  f"达标 {F0['goal_met']}/{F0['runs']} → {M0['goal_met']}/{M0['runs']}（不带记忆 → 带记忆）。两次运行之间没有修改任何代码或配置。"]
    load = config.VAR_DIR / "env" / f"load-{s['comparison_id']}.log"
    if load.exists():
        vals = [float(line.split("{")[1].split()[0]) for line in load.read_text().splitlines() if "{" in line]
        if vals:
            lines += ["", f"运行期间每 30 秒采样的系统 1 分钟负载（16 核）：中位数 {sorted(vals)[len(vals) // 2]:.0f}，范围 {min(vals):.0f}—{max(vals):.0f}。"
                      "同机还有一个常驻的本地模型服务（约占 2 核）和 iCloud 文件同步；两侧按任务交替运行，承受同样的环境。"]
    lines += ["", "观察（由数据生成）：", ""]
    note = narrative.stream_note(s)["lines"]
    lines += [f"- {note[0]}", f"- {note[1]}"]
    worse = [(fam, d) for fam, d in s["by_family"].items()
             if round(d["memory"]["final_speedup_median"] or 0, 2) < round(d["fresh"]["final_speedup_median"] or 0, 2)]
    for fam, d in worse:
        lines.append(f"- {FAMILY_ZH.get(fam, fam)}：带记忆一侧最终加速比中位数 {x(d['memory']['final_speedup_median'])} 低于不带记忆的 "
                     f"{x(d['fresh']['final_speedup_median'])}。复用的程序在新任务上复验达标就交付，不再为这个任务专门研究；"
                     "想继续提高要用学习模式（见[边界条件](legacy-runtime-rules.md)第 6 节）。")
    lines.append("")


def ablation_runs() -> dict[str, list[dict]]:
    out = {}
    for arm in ("on", "off"):
        ids = [r["run_id"] for r in db.all_rows("SELECT run_id FROM runs WHERE json_extract(config_json, '$.label') = ? AND status != 'running'"
                                                " ORDER BY started_at", (f"router ablation · {arm}",))]
        out[arm] = [report.build(i) for i in ids]
    return out


def section_ablation(lines: list[str]) -> None:
    ab = ablation_runs()
    if not (ab["on"] and ab["off"]):
        return
    on, off = compare._side(ab["on"]), compare._side(ab["off"])

    def small(reps):
        return sum(r["iterations"].get("small_model_requests", 0) for r in reps)
    lines += ["### 2.3 分流器对照：全新任务族直接用大模型 vs 先用本地小模型", "",
              "4 个 T 任务（两个新任务族，各有相近条件和新条件），都从 v19 出发（没有这两个任务族的经验），评测模式不写经验；"
              f"分流开启与关闭各运行 {len(ab['on']) // 4} 次，按任务交替先后。两侧配置只差分流器一项。", "",
              "| 指标 | 分流关闭（先用本地 Qwen） | 分流开启（直接用 GPT） |", "|---|---|---|",
              f"| 达标 / 运行 | {off['goal_met']}/{off['runs']} | {on['goal_met']}/{on['runs']} |",
              f"| 最终加速比中位数 | {x(off['final_speedup_median'])} | {x(on['final_speedup_median'])} |",
              f"| 模型请求合计（小模型 / 大模型） | {off['model_requests_total']}（{small(ab['off'])} / {off['large_model_requests_total']}） | "
              f"{on['model_requests_total']}（{small(ab['on'])} / {on['large_model_requests_total']}） |",
              f"| 按规则升级到 GPT | {off['upgrades_total']} | {on['upgrades_total']} |",
              f"| 失败候选 | {off['candidates_failed_total']} | {on['candidates_failed_total']} |",
              f"| 模型费用（估算） | {usd(off['cost_usd_total'])} | {usd(on['cost_usd_total'])} |",
              f"| 单次研究循环时长中位数 | {off['agent_loop_s_median']:.1f}s | {on['agent_loop_s_median']:.1f}s |",
              f"| 总耗时 | {off['wall_clock_s_total']:.0f}s | {on['wall_clock_s_total']:.0f}s |", "",
              "| 任务 | 分流关闭：达标 · 加速比 · 请求 · 循环时长 | 分流开启：达标 · 加速比 · 请求 · 循环时长 |", "|---|---|---|"]
    for t in ("T-L1", "T-L2", "T-I1", "T-I2"):
        def cell(reps):
            rs = [r for r in reps if r["task"]["task_id"] == t]
            return "；".join(f"{'✓' if r['outcome']['goal_met'] else '✕'} {x(r['outcome']['final_speedup'])} · {r['iterations']['model_requests']} 次 · "
                            f"{r['timing']['agent_loop_s']:.0f}s" for r in rs)
        lines.append(f"| {t} | {cell(ab['off'])} | {cell(ab['on'])} |")
    extra = ((on["cost_usd_total"] or 0) - (off["cost_usd_total"] or 0)) / max(1, on["runs"])
    lines += ["", f"观察：两侧都全部达标。直接用大模型时单次研究循环时长中位数 {off['agent_loop_s_median']:.0f}s → {on['agent_loop_s_median']:.0f}s，"
              f"总耗时 {off['wall_clock_s_total']:.0f}s → {on['wall_clock_s_total']:.0f}s，最终加速比中位数 {x(off['final_speedup_median'])} → "
              f"{x(on['final_speedup_median'])}，没有失败候选和升级；先用本地小模型时有 {off['candidates_failed_total']} 个候选失败、"
              f"{off['upgrades_total']} 次按规则升级。代价是费用 {usd(off['cost_usd_total'])} → {usd(on['cost_usd_total'])}，"
              f"平均每个新任务多 ${extra:.3f}。新问题的第一个答案会成为之后同类任务复用的起点（见 2.2 节），所以分流器把这笔钱花在第一次。"]
    lines.append("")


def section_research(lines: list[str], cs: dict) -> None:
    """RA view over all formal runs: how hypotheses fared and whether follow-ups built on earlier results."""
    groups = []
    if "S" in cs:
        s = cs["S"]
        for arm, name in (("memory", "带记忆"), ("fresh", "不带记忆")):
            groups.append((f"第三版 · S 任务流 · {name}", [r["run_id"] for p in s["positions"] for r in p["arms"][arm]]))
    groups.append(("第二版 · A 学习两轮", learn_runs(V2_LEARN)))
    for key, name in (("B2", "第二版 · B"), ("D", "第二版 · D"), (None, None), ("B", "第一版 · B"), ("C", "第一版 · C")):
        if key is None:
            groups.append(("第一版 · A 学习（v0 → v6）", learn_runs(V1_LEARN)))
        elif key in cs:
            c = cs[key]
            for side in (c["snapshot_a"], c["snapshot_b"]):
                groups.append((f"{name} · {side}", [r["run_id"] for t in c["tasks"] for r in c["per_task"][t][side]["runs"]]))
    lines += ["## 5. 研究过程统计", "",
              "每个实验在执行前写下假设、预期结果和验证方法（模型候选由模型写；复用的程序由程序依据经验记录写明来源、原实测结果和条件差异）；"
              "判定由程序依据随后的评测给出：得到支持（改善且达到当时目标）、部分支持（改善未达目标）、被反驳（正确但没有改善）、未能检验（候选出错）。"
              "“引用此前候选”统计后续模型假设的文字里是否点名同一运行中更早的候选编号，只是反馈驱动的下限。", "",
              "| 批次 · 快照 | 运行 | 实验 | 其中复用（得到支持） | 支持 | 部分支持 | 反驳 | 未能检验 | 后续模型实验引用此前候选 | 取证 | 升级 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, ids in groups:
        if not ids:
            continue
        a = research.aggregate([report.build(i) for i in ids])
        lines.append(f"| {name} | {a['runs']} | {a['experiments']} | {a['reuse_experiments']}（{a['reuse_supported']}） | {a['supported']} | "
                     f"{a['partial']} | {a['refuted']} | {a['untestable']} | {a['follow_ups_citing_prior']} / {a['follow_ups']} | "
                     f"{a['evidence_calls']} | {a['upgrades']} |")
    lines.append("")


def section_summary(lines: list[str], cs: dict) -> None:
    if "S" in cs:
        s = cs["S"]
        F, M = s["sides"]["fresh"], s["sides"]["memory"]
        lines += ["## 1. 摘要", "",
                  f"**第三版（当前）：分流器 + 在线记忆，3 个任务族。** 封存的 S 任务流 {len(s['tasks'])} 个任务 × {s['repeats']} 次重放，"
                  "同一配置，只比较是否积累经验：", "",
                  "| | 达标 | 最终加速比中位数 | 大模型请求 | 没有调用模型的运行 | 模型费用 | 循环时长中位数 | 总耗时 |", "|---|---|---|---|---|---|---|---|",
                  f"| 不带记忆 | {F['goal_met']}/{F['runs']} | {x(F['final_speedup_median'])} | {F['large_model_requests_total']} | "
                  f"{F['runs_without_model_request']} | {usd(F['cost_usd_total'])} | {F['agent_loop_s_median']:.1f}s | {F['wall_clock_s_total']:.0f}s |",
                  f"| 带记忆 | {M['goal_met']}/{M['runs']} | {x(M['final_speedup_median'])} | {M['large_model_requests_total']} | "
                  f"{M['runs_without_model_request']} | {usd(M['cost_usd_total'])} | {M['agent_loop_s_median']:.1f}s | {M['wall_clock_s_total']:.0f}s |", "",
                  "**第一版与第二版：分组聚合任务族上的留出对照。**", ""]
    else:
        lines += ["## 1. 摘要", ""]
    lines += [
              "同一 Agent、同一配置，只换经验快照（v0 无经验 vs 学习后的快照）；每批 6 个未参与学习的任务 × 3 次，全部运行计入。",
              "第一版的经验是文字记录（条件、改动、实测结果）；第二版在此之上保存完整程序，新任务先由程序复验最接近的已验证程序，"
              "评测运行复验达标即停、不调用模型；学习运行则以已知最佳为起点继续超越。", "",
              "| 批次 | 配置 | 达标 | 最终加速比中位数 | 模型请求中位数 | 升级到 GPT | GPT 费用 | 循环时长中位数 |", "|---|---|---|---|---|---|---|---|"]
    for key, name in (("C", "C 最终留出"), ("B2", "B 开发对照"), ("D", "D 封存留出")):
        if key not in cs:
            continue
        c = cs[key]
        a, b = c["snapshot_a"], c["snapshot_b"]
        A, B = c["sides"][a], c["sides"][b]
        ver = "第一版 · 文字经验" if key == "C" else "第二版 · 复用已验证程序"
        lines.append(f"| {name} | {ver}（{a} → {b}） | {A['goal_met']}/{A['runs']} → {B['goal_met']}/{B['runs']} | "
                     f"{x(A['final_speedup_median'])} → {x(B['final_speedup_median'])} | {g(A['model_requests_median'])} → {g(B['model_requests_median'])} | "
                     f"{A['upgrades_total']} → {B['upgrades_total']} | {usd(A['cost_usd_total'])} → {usd(B['cost_usd_total'])} | "
                     f"{A['agent_loop_s_median']:.0f}s → {B['agent_loop_s_median']:.0f}s |")
    lines.append("")


def main() -> None:
    lines = ["# 经验学习实验结果（第一至三版）", "",
             "数据由 `backend/scripts/write_results.py` 从运行记录生成。方法见[项目说明](../presentation/project-overview.md)。", ""]
    cs = comparisons()
    section_summary(lines, cs)
    if "S" in cs:
        lines += ["## 2. 第三版：分流器 + 在线记忆 + 3 个任务族（当前配置）", "",
                  "第二版只在一个任务族上验证。第三版新增两个任务族（访问日志统计、区间合并），并加入分流器：复用不达标时，"
                  "有同族相近成功经验的任务先用本地小模型，全新的任务族或没有相近成功经验的条件直接交给大模型。新增在线模式："
                  "像评测一样交付，交付后把验证过的结果写入经验，下一个相似任务先复用。规则与边界见[边界条件](legacy-runtime-rules.md)。"
                  "S 批和 T 批在第三版任何运行之前提交并锁定（提交 `7f9cace`）。", ""]
        section_tuning(lines)
        section_stream(lines, cs["S"])
        section_ablation(lines)
    lines += ["## 3. 第二版：复用已验证程序（分组聚合）", "",
              "第一版的 C 对照显示：有经验后请求和费用下降，但最终加速比中位数从 1.41× 降到 1.29×。原因有二：经验里的程序要由模型花一次请求重新写出；"
              "Qwen 写出的版本一达标循环就停止，用不上 GPT 找到的更快方案。第二版据此修改（配置指纹随之改变，两边对照仍用同一配置）："
              "经验保存完整程序，程序在首次模型请求前复验最多 3 个条件最接近的已验证程序。D 批在第二版实现之前封存（见 `backend/tasks/spec.json` 的提交记录），"
              "只在 B 上定型后运行一次。", ""]
    section_learning_v2(lines)
    for key in ("B2", "D"):
        if key in cs:
            section_comparison(lines, key, cs[key])
        else:
            lines += [f"### {TITLES[key]}", "", "尚未完成。", ""]
    lines += ["## 4. 第一版：文字经验（历史配置，结论保留）", ""]
    section_learning(lines)
    for key in ("B", "C"):
        if key in cs:
            section_comparison(lines, key, cs[key])
    section_research(lines, cs)
    lines += ["## 6. 说明", "",
              "- 三版的配置指纹不同（提示词版本、复用策略、分流器），各自内部对照的两侧使用同一配置；跨版本的数字只用于说明改动前后，不当作同一对照。",
              "- S 任务流先评测、再学习：每个任务完成测试后才写入经验。",
              "- 第一版 C 批的结果是第二版修改的依据，因此第二版的最终验收改用新封存的 D 批；B 批两版都作开发对照。",
              "- B、C、D 的 3 次重复衡量固定快照下的运行波动；S 任务流的 3 次重放每次都从起点重新学习，重复的是学习过程本身。",
              "- 所有运行都计入，包括失败、无收益和预算耗尽的运行；没有挑选任务或样本。",
              "- GPT 费用按 2026-11-13 官方价表估算；本地 Qwen 无 API 费用，机器成本未核算。",
              "- 计时在同一台 Mac 的 Docker（OrbStack）中串行进行；A-05 学习运行期间曾有测试进程并发，已在该运行的事件中标注。", ""]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
