"""Research view of a run (RA-01—RA-04): the research task as fixed before the run started, and every experiment
with the hypothesis, prediction and verification method the model recorded before execution, the measured result,
and a verdict. Verdicts are assigned by the program from the evaluation that followed, never by the model."""

from __future__ import annotations

from . import db

QUESTION = "在输出完全正确的前提下，能否让这段分组聚合程序在该工作负载上至少快 {target}×？"
SCOPE = ("只能整体替换程序文件；仅 Python 标准库；代码不超过 {max_code_bytes} 字节；输入经 stdin、输出到 stdout；"
         "评测器、参考输出和最终测试数据不可见、不可改")
TOOLS = [
    ("analyze", "分析：写下推理与计划，不执行"),
    ("get_evidence", "取证：在沙箱中对某个候选做 cProfile，返回热点"),
    ("propose_candidate", "提出候选：提交完整程序，程序立即验证"),
    ("run_validation", "运行验证：重新评测已有候选"),
    ("finish", "结束：交付当前最佳已验证候选"),
]
VERIFICATION = ("开发数据正确性 + 7 个公开契约用例 + 基线与候选各预热一次、交替计时 5 轮；"
                "全部候选样本快于全部基线样本才算改善，加速比 = 两者中位数之比")
VERDICTS = {
    "supported": "得到支持",
    "partial": "部分支持（改善，但未达目标）",
    "refuted": "被反驳（正确但没有改善）",
    "untestable": "未能检验（候选出错）",
    "untested": "未评测（预算或运行结束）",
}


def definition(rep: dict) -> dict:
    """RA-01: question, goal, baseline, allowed scope, tools and budget — all fixed when the run was created."""
    lim = rep["config"]["limits"]
    dev = rep["task"]["dev_params"]
    base = db.one("SELECT baseline_median_s FROM evaluations WHERE run_id = ? AND dataset = 'dev' AND baseline_median_s IS NOT NULL"
                  " ORDER BY started_at LIMIT 1", (rep["run_id"],))
    final = rep["final_evaluation"]
    return {
        "question": QUESTION.format(target=rep["task"]["target_min_speedup"]),
        "goal": f"输出全对；全部样本快于基线；加速比 ≥ {rep['task']['target_min_speedup']}×",
        "workload": f"{dev['rows']:,} 行 · {dev['keys']:,} 个 key · {dev['order']} · 偏斜 {dev['skew']}",
        "baseline": {
            "program": "c0：csv + 两个 dict + sorted（初始程序，正确）",
            "dev_median_s": base["baseline_median_s"] if base else None,
            "final_median_s": final["baseline_median_s"] if final else None,
        },
        "scope": SCOPE.format(max_code_bytes=lim["max_code_bytes"]),
        "tools": [{"action": a, "label": t} for a, t in TOOLS],
        "verification": VERIFICATION,
        "budget": {"model_requests": lim["max_model_requests"], "candidates": lim["max_candidates"],
                   "loop_s": lim["wall_clock_s"], "request_timeout_s": lim["model_request_timeout_s"],
                   "measurement_timeout_s": lim["measurement_timeout_s"]},
        "final_test": "循环结束后冻结最佳候选，在隐藏的最终数据上测一次；结果不回流到研究过程",
    }


def _verdict(res: dict, target: float) -> str:
    if not res:
        return "untested"
    if res.get("status") != "passed":
        return "untestable"
    if not res.get("improved"):
        return "refuted"
    return "supported" if (res.get("speedup") or 0) >= target else "partial"


def experiments(rep: dict) -> list[dict]:
    """RA-03: one row per proposed candidate, in order; `then` is what the program decided after the result."""
    steps = rep["steps"]
    target = rep["task"]["target_min_speedup"]
    out = []
    for i, s in enumerate(steps):
        if s["action"] != "propose_candidate" or not s["candidate_id"]:
            continue
        check = next((x for x in steps[i + 1:] if x["action"] == "run_validation" and x["candidate_id"] == s["candidate_id"]), None)
        res = check["result"] if check else {}
        failure = res.get("failure") or {}
        out.append({
            "candidate_id": s["candidate_id"], "step": s["seq"],
            "hypothesis": s["hypothesis"], "purpose": s["purpose"],
            "expected": s["expected_result"], "verification": s["verification"],
            "result": {"status": res.get("status"), "speedup": res.get("speedup"), "improved": res.get("improved"),
                       "failure": failure.get("category"), "contract_case": failure.get("contract_case")},
            "verdict": _verdict(res, target),
            "then": check["next_decision"] if check else None,
            "evaluation_id": res.get("evaluation_id"),
        })
    return out


def summarize(rep: dict) -> dict:
    exps = experiments(rep)
    counts = {k: sum(1 for e in exps if e["verdict"] == k) for k in VERDICTS}
    return {"definition": definition(rep), "experiments": exps, "verdicts": counts, "verdict_labels": VERDICTS}


def aggregate(reports: list[dict]) -> dict:
    """Totals over many runs: verdicts, and how often a follow-up hypothesis names an earlier candidate of the same run
    (a plain-text check that the next experiment was built on the previous result, not a fixed script)."""
    import re

    out = {k: 0 for k in VERDICTS}
    out.update(runs=len(reports), experiments=0, follow_ups=0, follow_ups_citing_prior=0, evidence_calls=0, upgrades=0)
    for rep in reports:
        exps = rep["research"]["experiments"]
        out["experiments"] += len(exps)
        out["evidence_calls"] += rep["iterations"]["evidence_calls"]
        out["upgrades"] += rep["iterations"]["upgrades"]
        for k, v in rep["research"]["verdicts"].items():
            out[k] += v
        for i, e in enumerate(exps[1:], 1):
            out["follow_ups"] += 1
            prior = {p["candidate_id"] for p in exps[:i]}
            text = f"{e['purpose'] or ''} {e['hypothesis'] or ''}"
            if prior & set(re.findall(r"\bc\d+\b", text)):
                out["follow_ups_citing_prior"] += 1
    return out
