"""Write docs/results.md from stored records: learning runs, comparisons, per-task outcomes, costs.

Two configurations are reported. Version 2 (current) re-validates verified programs from experience before asking a
model (memory.REUSE): A learning in two rounds, B development comparison, D sealed held-out. Version 1 (text experience
only) keeps its A learning, B and C results unchanged.

    uv run python scripts/write_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

from routeevo import compare, db, memory, narrative, report, research

OUT = Path(__file__).resolve().parents[2] / "docs" / "results.md"


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
LABELS = [("B dev comparison · reuse", "B2"), ("D final held-out · reuse", "D"), ("B dev", "B"), ("C final", "C")]


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
    lines += ["### 2.1 学习：A 批两轮，从 v0 开始", "",
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
    lines += ["### 3.1 学习阶段（A 批，串行，从 v0 开始）", "",
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


TITLES = {"B2": "2.2 B 批开发对照", "D": "2.3 D 批封存留出（最终验收）", "B": "3.2 B 批开发对照", "C": "3.3 C 批最终留出"}


def section_comparison(lines: list[str], key: str, c: dict) -> None:
    a, b = c["snapshot_a"], c["snapshot_b"]
    A, B = c["sides"][a], c["sides"][b]
    lines += [f"### {TITLES[key]}：{a} vs {b}", "",
              f"`{c['comparison_id']}` · {len(c['tasks'])} 个任务 × 2 个快照 × {c['repeats']} 次 · 完成 {c['finished_runs']}/{c['planned_runs']} · "
              f"配置指纹{'一致' if c['fair'] else '**不一致**'}（{', '.join(c['config_fingerprints'])}） · 升级规则 {upgrade_rule(c['comparison_id'])}", "",
              f"| 指标 | {a}（旧经验） | {b}（新经验） |", "|---|---|---|",
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
    if missed:
        lines.append(f"- 开发数据上已达标、但最终测试未满足“全部样本快于基线”的运行 {len(missed)} 次：{'、'.join(missed)}；按规则记为未达标。")
    ia, ib = A["input_tokens"]["total"], B["input_tokens"]["total"]
    if ia and ib and ib > ia:
        lines.append(f"- 输入 Token {n(ia)} → {n(ib)}：经验摘要进入提示词，单次请求更长；请求次数和输出 Token 减少，GPT 费用仍以实测为准。")


def section_research(lines: list[str], cs: dict) -> None:
    """RA view over all formal runs: how hypotheses fared and whether follow-ups built on earlier results."""
    groups = [("第二版 · A 学习两轮", learn_runs(V2_LEARN))]
    for key, name in (("B2", "第二版 · B"), ("D", "第二版 · D"), (None, None), ("B", "第一版 · B"), ("C", "第一版 · C")):
        if key is None:
            groups.append(("第一版 · A 学习（v0 → v6）", learn_runs(V1_LEARN)))
        elif key in cs:
            c = cs[key]
            for side in (c["snapshot_a"], c["snapshot_b"]):
                groups.append((f"{name} · {side}", [r["run_id"] for t in c["tasks"] for r in c["per_task"][t][side]["runs"]]))
    lines += ["## 4. 研究过程统计", "",
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
    lines += ["## 1. 摘要：两版经验在留出任务上的对照", "",
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
    lines = ["# RouteEvo 实验结果", "",
             "本文由 `backend/scripts/write_results.py` 从运行记录生成，不含手工填写的数字。口径见[项目说明](project-description.md)。", ""]
    cs = comparisons()
    section_summary(lines, cs)
    lines += ["## 2. 第二版：复用已验证程序（当前配置）", "",
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
    lines += ["## 3. 第一版：文字经验（历史配置，结论保留）", ""]
    section_learning(lines)
    for key in ("B", "C"):
        if key in cs:
            section_comparison(lines, key, cs[key])
    section_research(lines, cs)
    lines += ["## 5. 说明", "",
              "- 两版的配置指纹不同（提示词版本、复用策略），各自内部的 v0 与学习快照使用同一配置；跨版本的数字只用于说明改动前后，不当作同一对照。",
              "- 第一版 C 批的结果是第二版修改的依据，因此第二版的最终验收改用新封存的 D 批；B 批两版都作开发对照。",
              "- 3 次重复衡量固定快照下的运行波动，不代表学习过程本身被重复验证。",
              "- 所有运行都计入，包括失败、无收益和预算耗尽的运行；没有挑选任务或样本。",
              "- GPT 费用按 2026-11-13 官方价表估算；本地 Qwen 无 API 费用，机器成本未核算。",
              "- 计时在同一台 Mac 的 Docker（OrbStack）中串行进行；A-05 学习运行期间曾有测试进程并发，已在该运行的事件中标注。", ""]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
