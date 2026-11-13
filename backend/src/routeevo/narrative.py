"""Human-readable exports filled only from stored records: a run's research record and a comparison's
three-line evolution note. Nothing here is written by a model."""

from __future__ import annotations

from pathlib import Path

from . import compare, config, memory, report

ACTION_ZH = {"analyze": "分析", "get_evidence": "取证", "propose_candidate": "提出候选", "run_validation": "验证",
             "finish": "结束", "upgrade_model": "升级模型", "model_request": "模型请求", "invalid": "无效回复"}
STOP_ZH = {"goal_reached": "目标达成", "budget_exhausted": "预算耗尽", "agent_finished": "Agent 主动结束",
           "user_stopped": "用户停止", "model_api_error": "模型接口错误", "environment_error": "环境错误",
           "internal_error": "内部错误"}


DECISION_ZH = {"continue": "继续", "validate candidate": "验证候选", "re-measure candidate": "重新测量",
               "continue with feedback": "带着反馈继续", "continue with large model": "改用大模型继续",
               "upgrade to large model, continue": "升级到大模型并继续", "stop": "停止",
               "retry with a new request if budget allows": "预算允许则重发请求"}


def _decision(d: str) -> str:
    if d.startswith("stop: "):
        return "停止：" + STOP_ZH.get(d[6:], d[6:])
    return DECISION_ZH.get(d, d)


def _rel(path: str) -> str:
    try:
        return str(Path(path).relative_to(config.BACKEND_DIR))
    except ValueError:
        return path


def _x(v) -> str:
    return "—" if v is None else f"{v:.2f}×"


def _usd(v) -> str:
    return "未知" if v is None else f"${v:.4f}"


def _cell(text) -> str:
    return (str(text) if text is not None else "").replace("|", "\\|").replace("\n", " ")[:160]


def run_markdown(run_id: str) -> str:
    r = report.build(run_id)
    t, o, u, tm = r["task"], r["outcome"], r["usage"]["total"], r["timing"]
    lines = [
        f"# 运行记录 {run_id}",
        "",
        f"- 任务：{t['task_id']}（{t['split']} 批），目标：输出全对且加速比 ≥ {t['target_min_speedup']}×",
        f"- 模式：{'学习' if r['mode'] == 'learn' else '评测'}；读取经验快照：{r['snapshot_id']}；配置指纹：`{r['config_fingerprint']}`",
        f"- 结论：**{o['summary']}**（终止：{STOP_ZH.get(r['stop_reason'], r['stop_reason'])}）",
        f"- 状态拆分：候选运行完成 {o['candidate_ran']} · 开发验证通过 {o['dev_validation_passed']} · "
        f"指标改善 {o['dev_improved']} · 最终测试达标 {o['goal_met']}",
    ]
    if r["scripted_model"]:
        lines.append(f"- 注意：{'+'.join(r['scripted_model'])} 角色使用脚本模型，仅用于功能检查，不作为效果证据")
    lines += ["", "## 研究过程", "", "| # | 执行者 | 动作 | 状态 | 目的 / 假设 | 反馈与下一步 |", "|---|---|---|---|---|---|"]
    for s in r["steps"]:
        res = s["result"]
        fb = []
        if res.get("speedup") is not None:
            fb.append(f"加速比 {_x(res['speedup'])}{'，改善' if res.get('improved') else ''}")
        if res.get("failure"):
            f = res["failure"]
            fb.append(f"{f.get('category')}{(' · ' + str(f.get('contract_case'))) if f.get('contract_case') else ''}")
        if s["next_decision"]:
            fb.append(f"→ {_decision(s['next_decision'])}")
        what = s["purpose"] or ""
        if s["hypothesis"]:
            what += f"（假设，未验证：{s['hypothesis']}）"
        lines.append(f"| {s['seq']} | {'模型' if s['actor'] == 'model' else '程序'} | {ACTION_ZH.get(s['action'], s['action'])} | "
                     f"{s['status']} | {_cell(what)} | {_cell('；'.join(fb))} |")
    lines += ["", "## 候选", "", "| 候选 | 来源 | 父候选 | 开发验证 | 加速比 | 代码 |", "|---|---|---|---|---|---|"]
    for c in r["candidates"]:
        ev = c["dev_evaluations"][-1] if c["dev_evaluations"] else {}
        sp = 1.0 if c["candidate_id"] == "c0" else ev.get("speedup")
        lines.append(f"| {c['candidate_id']}{' ★' if r['best_candidate'] and c['candidate_id'] == r['best_candidate']['candidate_id'] else ''} | "
                     f"{c['origin']} | {c['parent_candidate_id'] or '—'} | {ev.get('status', '—')} | {_x(sp)} | `{_rel(c['code_path'])}` |")
    fe = r["final_evaluation"]
    lines += ["", "## 独立最终测试", ""]
    lines.append(f"- {fe['candidate_id'] if fe else '—'}：{fe['status'] if fe else '未运行'}，加速比 {_x(fe['speedup']) if fe else '—'}"
                 + (f"（候选中位 {fe['candidate_median_s']:.3f}s / 基线中位 {fe['baseline_median_s']:.3f}s）" if fe and fe.get("candidate_median_s") else ""))
    lines += ["", "## 读取的经验", ""]
    if r["experience"]["read"]:
        for e in r["experience"]["read"]:
            lines.append(f"- #{e['rank']} `{e['experience_id']}`（{e['outcome']}，{e['matching_features']}/5 特征匹配，来自 {e['task_id']}）")
    else:
        lines.append(f"- 无（{r['snapshot_id']} 中没有匹配当前工作负载的经验）")
    if r["experience"]["published_snapshot_id"]:
        lines.append(f"- 本次学习发布 {r['experience']['published_snapshot_id']}，新增 {len(r['experience']['published_experiences'])} 条")
    lines += [
        "", "## 资源", "",
        f"- 模型请求 {r['iterations']['model_requests']} 次，升级 {r['iterations']['upgrades']} 次；候选 {r['iterations']['candidates_proposed']} 个"
        f"（通过 {r['iterations']['candidates_passed']}，改善 {r['iterations']['candidates_improved']}，失败 {r['iterations']['candidates_failed']}）",
        f"- Token：输入 {u['input_tokens']}，输出 {u['output_tokens']}（推理 {u['reasoning_tokens']}）；费用 {_usd(u['cost_usd'])}（{u['cost_status']}）",
        f"- 时间：总 {tm['wall_clock_total_s']}s，循环 {tm['agent_loop_s']}s / 上限 {tm['agent_loop_limit_s']}s，模型等待 {tm['model_wait_s']}s，"
        f"开发验证 {tm['dev_evaluation_s']}s，最终测试 {tm['final_evaluation_s']}s",
        "", "## 复现", "",
        f"- 重跑：`{r['reproduce']['run_again']}`",
        f"- 复核最佳产物：`{r['reproduce']['recheck_best']}`" if r["reproduce"]["recheck_best"] else "- 无有效产物",
    ]
    return "\n".join(lines) + "\n"


def evolution_note(comparison_id: str) -> dict:
    """The 日新 three-line note: what was compared, what was learned, how to roll back — each tied to evidence."""
    c = compare.summarize(comparison_id)
    a, b = c["snapshot_a"], c["snapshot_b"]
    A, B = c["sides"].get(a), c["sides"].get(b)
    lc = c["learning_cost"]
    diff = memory.compare_snapshots(a, b)
    added = [memory.experience(e) for e in diff["added"]]
    by = {k: sum(1 for e in added if e["outcome"] == k) for k in ("success", "no_gain", "failure")}
    if not (A and B):
        return {"comparison_id": comparison_id, "lines": ["对照尚未产生结果。"], "evidence": {}}
    line1 = (f"比什么：在固定质量约束（输出全对、改善超出噪声、加速比 ≥ 1.10 才算达标）下，用同一批 {len(c['tasks'])} 个留出任务 × "
             f"{c['repeats']} 次对比 {a} 与 {b}：达标 {A['goal_met']}/{A['runs']} → {B['goal_met']}/{B['runs']}，"
             f"最终加速比中位数 {_x(A['final_speedup_median'])} → {_x(B['final_speedup_median'])}，"
             f"输出 Token {A['output_tokens']['total']} → {B['output_tokens']['total']}，费用 {_usd(A['cost_usd_total'])} → {_usd(B['cost_usd_total'])}，"
             f"总耗时 {A['wall_clock_s_total']:.0f}s → {B['wall_clock_s_total']:.0f}s；"
             + (f"学习成本另计 {_usd(lc.get('cost_usd'))} / {lc.get('wall_clock_s', 0):.0f}s。" if lc.get("in_lineage") else "学习成本不在同一版本链上，未计入。"))
    best = sorted([e for e in added if e["outcome"] == "success"], key=lambda e: -(e["result"]["speedup"] or 0))[:1]
    worst = [e for e in added if e["outcome"] == "failure"][:1]
    examples = []
    if best:
        examples.append(f"成功例 {best[0]['conditions']['task_id']}：{', '.join(best[0]['action']['code_features'].get('calls', [])[:5])} 实测 {_x(best[0]['result']['speedup'])}")
    if worst:
        examples.append(f"失败例 {worst[0]['conditions']['task_id']}：{worst[0]['result']['status']}")
    line2 = (f"学到什么：{a} → {b} 新增 {len(added)} 条已验证经验（成功 {by['success']}、无收益 {by['no_gain']}、失败 {by['failure']}）"
             + (f"，{'；'.join(examples)}" if examples else "")
             + f"；行动变化：模型请求中位数 {A['model_requests_median']} → {B['model_requests_median']}，"
             f"升级到 GPT {A['upgrades_total']} → {B['upgrades_total']} 次，失败候选 {A['candidates_failed_total']} → {B['candidates_failed_total']} 个。")
    line3 = (f"如何回退：在界面「04 版本管理」或执行 `uv run routeevo snapshots activate {a} --reason 回退` 把生效快照切回 {a}；"
             f"之后的运行读取 {a} 并从相同初始程序开始，{b} 及全部运行记录保留可查。")
    return {"comparison_id": comparison_id, "fair": c["fair"], "scripted_model": c["scripted_model"],
            "lines": [line1, line2, line3],
            "evidence": {"comparison": comparison_id, "added_experiences": diff["added"], "learn_runs": lc.get("learn_runs", [])}}
