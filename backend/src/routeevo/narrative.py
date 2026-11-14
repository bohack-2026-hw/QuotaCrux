"""Human-readable exports filled only from stored records: a run's research record and a comparison's
three-line evolution note. Nothing here is written by a model."""

from __future__ import annotations

from pathlib import Path

from . import compare, config, memory, report

ACTION_ZH = {"analyze": "分析", "get_evidence": "取证", "propose_candidate": "提出候选", "run_validation": "验证",
             "finish": "结束", "upgrade_model": "升级模型", "model_request": "模型请求", "invalid": "无效回复",
             "reuse_candidate": "复用已验证程序", "set_target": "提高本次目标", "route_model": "分流"}
MODE_ZH = {"learn": "学习", "eval": "评测", "online": "在线（交付并写入经验）"}
ROUTE_ZH = {"reuse": "复用直接交付", "familiar": "相近经验 → 本地小模型", "new_family": "全新任务族 → 大模型",
            "new_conditions": "新条件 → 大模型", "router_off": "分流关闭 → 小模型", "no_model_request": "未请求模型"}
STOP_ZH = {"goal_reached": "开发数据达标", "budget_exhausted": "预算耗尽", "agent_finished": "Agent 主动结束",
           "user_stopped": "用户停止", "model_api_error": "模型接口错误", "environment_error": "环境错误",
           "internal_error": "内部错误"}


STATUS_ZH = {"passed": "通过", "submitted": "已提交", "done": "完成", "requested": "已请求", "wrong_output": "输出错误",
             "format_error": "格式错误", "contract_violation": "违反契约", "runtime_error": "运行错误", "timeout": "超时",
             "memory_limit": "内存超限", "output_limit": "输出超限", "compile_error": "编译错误",
             "static_check_failed": "静态检查失败", "unstable": "结果不稳定", "sandbox_error": "环境错误",
             "baseline_failed": "基线失败", "checker_error": "校验器错误", "invalid_action": "无效动作", "api_error": "接口错误",
             "unusable_reply": "回复不可用", "tool_failed": "工具失败"}

DECISION_ZH = {"continue": "继续", "validate candidate": "验证候选", "re-measure candidate": "重新测量",
               "continue with feedback": "带着反馈继续", "continue with large model": "改用大模型继续",
               "upgrade to large model, continue": "升级到大模型并继续", "stop": "停止",
               "retry with a new request if budget allows": "预算允许则重发请求",
               "upgrade rule met but no model requests left": "满足升级条件，但模型请求已用完",
               "validate re-used program": "复验", "validate next re-used program": "复验下一个",
               "re-use finished": "复用复验结束",
               "continue with the model to beat the best known program": "交给模型，尝试超越已知最佳",
               "start model requests on the small model": "先用本地小模型", "start model requests on the large model": "直接用大模型"}


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


def _g(v) -> str:
    return "—" if v is None else f"{v:g}"


def _cell(text) -> str:
    return (str(text) if text is not None else "").replace("|", "\\|").replace("\n", " ")[:160]


def run_markdown(run_id: str) -> str:
    r = report.build(run_id)
    t, o, u, tm = r["task"], r["outcome"], r["usage"]["total"], r["timing"]
    is_score = t["objective"]["metric"] == "score"
    metric = "原始得分" if is_score else "加速比"
    lines = [
        f"# 研究记录 {run_id}",
        "",
        f"- 任务：{t['task_id']}（{t['split']} 批，{r['research']['definition']['workload']}），目标：{r['research']['definition']['goal']}",
        f"- 模式：{MODE_ZH.get(r['mode'], r['mode'])}；读取经验快照：{r['snapshot_id']}；配置指纹：`{r['config_fingerprint']}`",
        f"- 结论：**{o['summary']}**（终止：{STOP_ZH.get(r['stop_reason'], r['stop_reason'])}）",
        f"- 状态拆分：候选运行完成 {o['candidate_ran']} · 开发验证通过 {o['dev_validation_passed']} · "
        f"指标改善 {o['dev_improved']} · 最终测试达标 {o['goal_met']}",
    ]
    if r["scripted_model"]:
        lines.append(f"- 注意：{'+'.join(r['scripted_model'])} 角色使用脚本模型，仅用于功能检查，不作为效果证据")
    d = r["research"]["definition"]
    b = d["budget"]
    base = d["baseline"]
    lines += ["", "## 研究任务（运行开始前固定）", "",
              f"- 研究问题：{d['question']}",
              f"- 工作负载（开发数据画像）：{d['workload']}",
              f"- 基线：{base['program']}；开发数据中位耗时 {base['dev_median_s']:.3f}s" if base["dev_median_s"] else f"- 基线：{base['program']}",
              f"- 目标与质量约束：{d['goal']}",
              f"- 允许修改：{d['scope']}",
              f"- 工具：{'；'.join(t['label'] for t in d['tools'])}",
              f"- 验证方法：{d['verification']}",
              f"- 预算：模型请求 {b['model_requests']} 次、候选 {b['candidates']} 个、循环 {b['loop_s']:.0f}s、单次请求 {b['request_timeout_s']:.0f}s、单次测量 {b['measurement_timeout_s']:.0f}s",
              f"- 独立验收：{d['final_test']}"]
    lines += ["", "## 研究过程", "", "| # | 执行者 | 动作 | 状态 | 目的 / 假设 | 反馈与下一步 |", "|---|---|---|---|---|---|"]
    for s in r["steps"]:
        res = s["result"]
        fb = []
        if res.get("objective"):
            fb.append(f"原始得分 {res['objective']['value']}，基线 {res['objective']['baseline']}")
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
                     f"{STATUS_ZH.get(s['status'], s['status'])} | {_cell(what)} | {_cell('；'.join(fb))} |")
    lines += ["", "## 假设与实验", "",
              "每个候选提交前写下假设、预期结果和验证方法（复用的程序由程序依据经验记录写明，模型候选由模型写）；"
              "判定由程序根据随后的评测给出，不由模型自评：改善且达到当时目标 = 得到支持；改善但未达目标 = 部分支持；"
              "正确但没有改善 = 被反驳；候选出错 = 未能检验。", "",
              "| 候选 | 假设（事前，未验证） | 预期 | 实测 | 判定 | 之后 |", "|---|---|---|---|---|---|"]
    for e in r["research"]["experiments"]:
        res = e["result"]
        measured = f"{res['status'] or '—'}{(' · ' + _x(res['speedup'])) if res['speedup'] is not None else ''}"
        if res.get("objective"):
            measured += f" · 原始得分 {res['objective']['value']}"
        if res["contract_case"]:
            measured += f" · {res['contract_case']}"
        tag = "（复用）" if e.get("kind") == "reuse" else ""
        lines.append(f"| {e['candidate_id']}{tag} | {_cell(e['hypothesis'] or e['purpose'])} | {_cell(e['expected'])} | {measured} | "
                     f"{r['research']['verdict_labels'][e['verdict']]} | {_decision(e['then'] or '')} |")
    if not r["research"]["experiments"]:
        lines.append("| — | 本次运行没有提出候选 | — | — | — | — |")
    lines += ["", "## 候选", "", f"| 候选 | 来源 | 父候选 | 开发验证 | {metric} | 代码 |", "|---|---|---|---|---|---|"]
    for c in r["candidates"]:
        ev = c["dev_evaluations"][-1] if c["dev_evaluations"] else {}
        sp = 1.0 if c["candidate_id"] == "c0" else ev.get("speedup")
        value = _g((ev.get("objective") or {}).get("value")) if is_score else _x(sp)
        lines.append(f"| {c['candidate_id']}{' ★' if r['best_candidate'] and c['candidate_id'] == r['best_candidate']['candidate_id'] else ''} | "
                     f"{c['origin']} | {c['parent_candidate_id'] or '—'} | {ev.get('status', '—')} | {value} | `{_rel(c['code_path'])}` |")
    fe = r["final_evaluation"]
    lines += ["", "## 独立最终测试", ""]
    value = (_g((fe.get("objective") or {}).get("value")) if is_score else _x(fe["speedup"])) if fe else "—"
    lines.append(f"- {fe['candidate_id'] if fe else '—'}：{fe['status'] if fe else '未运行'}，{metric} {value}"
                 + (f"（候选中位 {fe['candidate_median_s']:.3f}s / 基线中位 {fe['baseline_median_s']:.3f}s）" if fe and fe.get("candidate_median_s") else ""))
    lines += ["", "## 读取的经验", ""]
    if r["experience"]["read"]:
        for e in r["experience"]["read"]:
            lines.append(f"- #{e['rank']} `{e['experience_id']}`（{e['outcome']}，{e['matching_features']}/{(r['experience']['retrieval'] or {}).get('feature_count', 5)} 特征匹配，来自 {e['task_id']}）")
    else:
        lines.append(f"- 无（{r['snapshot_id']} 中没有匹配当前工作负载的经验）")
    if r["experience"]["published_snapshot_id"]:
        lines.append(f"- 本次学习发布 {r['experience']['published_snapshot_id']}，新增 {len(r['experience']['published_experiences'])} 条")
    lines += [
        "", "## 资源", "",
        f"- 模型请求 {r['iterations']['model_requests']} 次，升级 {r['iterations']['upgrades']} 次；候选 {r['iterations']['candidates_proposed']} 个"
        f"（通过 {r['iterations']['candidates_passed']}，改善 {r['iterations']['candidates_improved']}，失败 {r['iterations']['candidates_failed']}）"
        f"；复用已验证程序 {r['iterations'].get('programs_reused', 0)} 个（改善 {r['iterations'].get('programs_reused_improved', 0)}）",
        f"- Token：输入 {u['input_tokens']}，输出 {u['output_tokens']}（推理 {u['reasoning_tokens']}）；费用 {_usd(u['cost_usd'])}（{u['cost_status']}）",
        f"- 时间：总 {tm['wall_clock_total_s']}s，循环 {tm['agent_loop_s']}s / 上限 {tm['agent_loop_limit_s']}s，模型等待 {tm['model_wait_s']}s，"
        f"开发验证 {tm['dev_evaluation_s']}s，最终测试 {tm['final_evaluation_s']}s",
        "", "## 复现", "",
        f"- 重跑：`{r['reproduce']['run_again']}`",
        f"- 复核最佳产物：`{r['reproduce']['recheck_best']}`" if r["reproduce"]["recheck_best"] else "- 无有效产物",
    ]
    return "\n".join(lines) + "\n"


def evolution_note(comparison_id: str) -> dict:
    """Three-line note on what experience changed: what was compared, what was learned, how to roll back — each tied to evidence."""
    c = compare.summarize(comparison_id)
    if c.get("kind") == "stream":
        return stream_note(c)
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
             f"单次研究循环时长中位数 {A['agent_loop_s_median']:.0f}s → {B['agent_loop_s_median']:.0f}s，总耗时 {A['wall_clock_s_total']:.0f}s → {B['wall_clock_s_total']:.0f}s；"
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
             + (f"；{B['goal_met_from_reuse']} 次运行直接复用经验中的程序达标，{B['runs_without_model_request']} 次没有调用模型"
                if B.get("goal_met_from_reuse") else "")
             + f"；行动变化：模型请求中位数 {_g(A['model_requests_median'])} → {_g(B['model_requests_median'])}，"
             f"升级到 GPT {A['upgrades_total']} → {B['upgrades_total']} 次，失败候选 {A['candidates_failed_total']} → {B['candidates_failed_total']} 个。")
    line3 = (f"如何回退：在界面「版本」页或执行 `uv run routeevo snapshots activate {a} --reason 回退` 把生效快照切回 {a}；"
             f"之后的运行读取 {a} 并从相同初始程序开始，{b} 及全部运行记录保留可查。")
    return {"comparison_id": comparison_id, "fair": c["fair"], "scripted_model": c["scripted_model"],
            "lines": [line1, line2, line3],
            "evidence": {"comparison": comparison_id, "added_experiences": diff["added"], "learn_runs": lc.get("learn_runs", [])}}


def stream_note(c: dict) -> dict:
    """Three-line note for an online stream: what was compared, what accumulated, how to roll back."""
    M, F = c["sides"].get("memory"), c["sides"].get("fresh")
    if not (M and F and M["runs"] and F["runs"]):
        return {"comparison_id": c["comparison_id"], "lines": ["任务流尚未产生结果。"], "evidence": {}}
    fams = sorted({p["family"] for p in c["positions"]})
    start = c["start_snapshot"]
    line1 = (f"比什么：同一串 {len(c['tasks'])} 个任务（{len(fams)} 个任务族，按固定顺序出现）× {c['repeats']} 次重放，带记忆（在线模式：交付后"
             f"写入经验，下一个任务读取）与不带记忆（每个任务都只读 {start}）对比：达标 {F['goal_met']}/{F['runs']} → {M['goal_met']}/{M['runs']}，"
             f"最终加速比中位数 {_x(F['final_speedup_median'])} → {_x(M['final_speedup_median'])}，大模型请求 {F['large_model_requests_total']} → "
             f"{M['large_model_requests_total']} 次，费用 {_usd(F['cost_usd_total'])} → {_usd(M['cost_usd_total'])}，"
             f"单次研究循环时长中位数 {F['agent_loop_s_median']:.0f}s → {M['agent_loop_s_median']:.0f}s，总耗时 {F['wall_clock_s_total']:.0f}s → "
             f"{M['wall_clock_s_total']:.0f}s（不带记忆 → 带记忆）。")
    first, later = c["first_of_family"]["memory"], c["repeats_of_family"]["memory"]
    lf = c["repeats_of_family"]["fresh"]
    g = c["growth"]
    routes = "、".join(f"{ROUTE_ZH.get(k, k)} {v}" for k, v in sorted(M["routes"].items(), key=lambda kv: -kv[1]))
    line2 = (f"学到什么：每次重放从 {start} 出发，经验从 {g[0]['experiences_start']} 条增长到 "
             f"{'/'.join(str(x['experiences_end']) for x in g)} 条；新任务族首次出现时由分流器直接交给大模型，其余任务带记忆时 "
             f"{later['runs_without_model_request']}/{later['runs']} 次没有调用模型（不带记忆 {lf['runs_without_model_request']}/{lf['runs']}），"
             f"大模型请求 {lf['large_model_requests_total']} → {later['large_model_requests_total']} 次；带记忆一侧的分流：{routes}。"
             f"新任务族首次出现时两侧条件相同（都没有该族经验），两侧都直接用大模型，带记忆 {first['goal_met']}/{first['runs']} 达标。")
    line3 = (f"如何回退：任务流结束后生效版本已恢复为实验前的版本；任何一次重放产生的版本都可在「版本」页查看或设为生效，"
             f"`uv run routeevo snapshots activate {start} --reason 回退` 回到起点，全部运行记录保留可查。")
    return {"comparison_id": c["comparison_id"], "fair": c["fair"], "scripted_model": c["scripted_model"],
            "lines": [line1, line2, line3], "evidence": {"comparison": c["comparison_id"], "growth": g}}
