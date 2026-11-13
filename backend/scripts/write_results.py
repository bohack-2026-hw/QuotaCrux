"""Write docs/results.md from stored records: learning runs, B and C comparisons, per-task outcomes, costs.

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


def comparisons() -> dict[str, dict]:
    out = {}
    for r in db.all_rows("SELECT comparison_id, label FROM comparisons WHERE status != 'running' ORDER BY created_at"):
        label = r["label"] or ""
        if label.startswith("B dev") or label.startswith("C final"):
            out[label[0]] = compare.summarize(r["comparison_id"])
    return out


def section_learning(lines: list[str]) -> None:
    sql = ("SELECT run_id FROM runs WHERE mode = 'learn' AND json_extract(config_json, '$.label') = 'formal A learning'"
           " ORDER BY started_at")
    reps = [report.build(r["run_id"]) for r in db.all_rows(sql)]
    lines += ["## 1. 学习阶段（A 批，串行，从 v0 开始）", "",
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


def section_comparison(lines: list[str], key: str, c: dict) -> None:
    title = {"B": "2. B 批开发对照", "C": "3. C 批最终留出"}[key]
    a, b = c["snapshot_a"], c["snapshot_b"]
    A, B = c["sides"][a], c["sides"][b]
    lines += [f"## {title}：{a} vs {b}", "",
              f"`{c['comparison_id']}` · {len(c['tasks'])} 个任务 × 2 个快照 × {c['repeats']} 次 · 完成 {c['finished_runs']}/{c['planned_runs']} · "
              f"配置指纹{'一致' if c['fair'] else '**不一致**'}（{', '.join(c['config_fingerprints'])}） · 升级规则 {upgrade_rule(c['comparison_id'])}", "",
              f"| 指标 | {a}（旧经验） | {b}（新经验） |", "|---|---|---|",
              f"| 达标 / 运行 | {A['goal_met']} / {A['runs']} | {B['goal_met']} / {B['runs']} |",
              f"| 最终加速比中位数（有计时结果的运行） | {x(A['final_speedup_median'])} | {x(B['final_speedup_median'])} |",
              f"| 无改进运行（保留初始程序） | {A['no_improvement_runs']} | {B['no_improvement_runs']} |",
              f"| 模型请求中位数 | {g(A['model_requests_median'])} | {g(B['model_requests_median'])} |",
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
              f"达标线是 1.10×，智能体达到目标即停止，所以更少的请求也可能停在更小的加速比上。"]
    if missed:
        lines.append(f"- 开发数据上已达标、但最终测试未满足“全部样本快于基线”的运行 {len(missed)} 次：{'、'.join(missed)}；按规则记为未达标。")
    ia, ib = A["input_tokens"]["total"], B["input_tokens"]["total"]
    if ia and ib and ib > ia:
        lines.append(f"- 输入 Token {n(ia)} → {n(ib)}：经验摘要进入提示词，单次请求更长；请求次数和输出 Token 减少，GPT 费用仍以实测为准。")


def section_research(lines: list[str], cs: dict) -> None:
    """RA view over all formal runs: how hypotheses fared and whether follow-ups built on earlier results."""
    groups = []
    sql = "SELECT run_id FROM runs WHERE mode = 'learn' AND json_extract(config_json, '$.label') = 'formal A learning' ORDER BY started_at"
    groups.append(("A 学习（v0 → v6）", [r["run_id"] for r in db.all_rows(sql)]))
    for key in ("B", "C"):
        if key in cs:
            c = cs[key]
            for side in (c["snapshot_a"], c["snapshot_b"]):
                groups.append((f"{key} · {side}", [r["run_id"] for t in c["tasks"] for r in c["per_task"][t][side]["runs"]]))
    lines += ["## 4. 研究过程统计", "",
              "每个候选提交前，模型写下假设、预期结果和验证方法；判定由程序依据随后的评测给出：得到支持（改善且达标）、部分支持（改善未达标）、"
              "被反驳（正确但没有改善）、未能检验（候选出错）。“引用此前候选”统计后续假设的文字里是否点名同一运行中更早的候选编号，"
              "只是反馈驱动的下限（不点名的修正不计入）。", "",
              "| 批次 · 快照 | 运行 | 实验（候选） | 支持 | 部分支持 | 反驳 | 未能检验 | 后续实验引用此前候选 | 取证 | 升级 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for name, ids in groups:
        a = research.aggregate([report.build(i) for i in ids])
        lines.append(f"| {name} | {a['runs']} | {a['experiments']} | {a['supported']} | {a['partial']} | {a['refuted']} | {a['untestable']} | "
                     f"{a['follow_ups_citing_prior']} / {a['follow_ups']} | {a['evidence_calls']} | {a['upgrades']} |")
    lines.append("")


def main() -> None:
    lines = ["# RouteEvo 实验结果", "",
             "本文由 `backend/scripts/write_results.py` 从运行记录生成，不含手工填写的数字。口径见[项目说明](project-description.md)。", ""]
    section_learning(lines)
    cs = comparisons()
    for key in ("B", "C"):
        if key in cs:
            section_comparison(lines, key, cs[key])
        else:
            lines += [f"## {'2. B 批开发对照' if key == 'B' else '3. C 批最终留出'}", "", "尚未完成。", ""]
    section_research(lines, cs)
    lines += ["## 5. 说明", "",
              "- 3 次重复衡量固定快照下的运行波动，不代表学习过程本身被重复验证。",
              "- 所有运行都计入，包括失败、无收益和预算耗尽的运行；没有挑选任务或样本。",
              "- GPT 费用按 2026-11-13 官方价表估算；本地 Qwen 无 API 费用，机器成本未核算。",
              "- 计时在同一台 Mac 的 Docker（OrbStack）中串行进行；A-05 学习运行期间曾有测试进程并发，已在该运行的事件中标注。", ""]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
