"""Export the frozen second development pilot, preserving candidate bytes.

Copies only manifests, completed reports, candidate programs and AlgoTune licenses.
Research notes and summary are derived from the frozen reports and protocol audit.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path: Path):
    return json.loads(path.read_text())


def copy_verified(source: Path, target: Path, expected_sha: str | None = None) -> None:
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if expected_sha is not None and digest != expected_sha:
        raise ValueError(f"source SHA256 differs from frozen record: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError(f"exported SHA256 mismatch: {target}")


def metric(evaluation: dict):
    objective = evaluation.get("objective")
    return objective["value"] if objective else evaluation["speedup"]


def feedback(report: dict, evaluation_id: str) -> dict:
    return next(step["result"] for step in report["steps"] if step.get("evaluation_id") == evaluation_id)


def summarize(report: dict, audit: dict, input_rate: Decimal, output_rate: Decimal) -> dict:
    best = report["best_candidate"]
    best_evaluation = best["dev_evaluations"][-1]
    best_feedback = feedback(report, best_evaluation["evaluation_id"])
    timed = [(candidate["candidate_id"], evaluation) for candidate in report["candidates"]
             for evaluation in candidate["dev_evaluations"] if evaluation["speedup"] is not None]
    peak = max(timed, key=lambda item: item[1]["speedup"]) if timed else None
    usage = report["usage"]["total"]
    if usage["input_tokens_unknown_calls"] or usage["output_tokens_unknown_calls"]:
        raise ValueError(f"token usage is incomplete: {report['run_id']}")
    cost = (Decimal(usage["input_tokens"]) * input_rate + Decimal(usage["output_tokens"]) * output_rate) / 1_000_000
    timing = report["timing"]
    return {
        "run_id": report["run_id"], "task_id": report["task"]["task_id"], "family": report["task"]["family"],
        "mode": report["config"]["research_protocol"]["mode"], "status": report["status"],
        "model_requests": report["iterations"]["model_requests"],
        "candidates_proposed": report["iterations"]["candidates_proposed"],
        "candidates_passed": report["iterations"]["candidates_passed"],
        "unique_ast_candidates": audit["unique_ast_candidates"], "invalid_actions": audit["invalid_types"],
        "best_candidate": best["candidate_id"], "best_code_sha256": best["code_sha256"],
        "best_dev_passed_cases": best_feedback["passed_cases"], "dev_case_count": best_feedback["case_count"],
        "metric": report["task"]["objective"]["metric"], "accepted_dev_metric": metric(best_evaluation),
        "accepted_dev_improved": bool(best_evaluation["improved"]),
        "highest_raw_dev_speedup": peak[1]["speedup"] if peak else None,
        "highest_raw_dev_speedup_candidate": peak[0] if peak else None,
        "highest_raw_dev_speedup_improved": bool(peak[1]["improved"]) if peak else None,
        "highest_raw_dev_speedup_correct": bool(peak[1]["correct"]) if peak else None,
        "wall_clock_s": timing["wall_clock_total_s"], "model_wait_s": timing["model_wait_s"],
        "dev_evaluation_s": timing["dev_evaluation_s"], "container_startup_s": timing["container_startup_s"],
        "input_tokens": usage["input_tokens"], "cached_input_tokens": usage["cached_input_tokens"],
        "output_tokens": usage["output_tokens"], "total_tokens": usage["input_tokens"] + usage["output_tokens"],
        "estimated_cny": float(cost), "stop_reason": report["stop_reason"],
        "final_evaluated": report["outcome"]["final_evaluated"],
        "candidate_files_exported_and_sha256_verified": len(report["candidates"]),
    }


def cell(value) -> str:
    return ("—" if value is None else str(value)).replace("|", "\\|").replace("\n", " ")[:180]


def research_markdown(report: dict, summary: dict) -> str:
    lines = [f"# 研究记录 {report['run_id']}", "",
             f"- 任务：{summary['task_id']}；模式：{summary['mode']}；模型：{report['config']['models']['small']['model']}。",
             f"- 提示版本：{report['config']['prompt']['version']}；经验快照：{report['snapshot_id']}。",
             "- 范围：开发集预实验；最终数据未评测。",
             f"- 停止原因：{summary['stop_reason']}。", "", "## 保留结果", "",
             f"- 保留候选：[{summary['best_candidate']}](candidates/{summary['best_candidate']}.py)；"
             f"开发用例通过 {summary['best_dev_passed_cases']}/{summary['dev_case_count']}；"
             f"{summary['metric']} = {summary['accepted_dev_metric']}；改善判定：{summary['accepted_dev_improved']}。",
             f"- 全部候选的最高原始 speedup：{cell(summary['highest_raw_dev_speedup'])}；"
             f"候选：{cell(summary['highest_raw_dev_speedup_candidate'])}；"
             f"改善判定：{cell(summary['highest_raw_dev_speedup_improved'])}。",
             "- 原始 speedup 峰值与保留指标分别记录；保留方案须通过正确性及选择规则。", "", "## 研究过程", "",
             "| 步骤 | 执行者 | 动作 | 状态 | 目的或结果 |", "|---|---|---|---|---|"]
    for step in report["steps"]:
        result = step["result"]
        detail = step["purpose"]
        if step.get("evaluation_id"):
            detail = f"{step['candidate_id']}: {result.get('passed_cases')}/{result.get('case_count')} cases; metric={metric(result)}; improved={result.get('improved')}"
        elif step["status"] == "invalid_action":
            detail = f"{result['kind']}: {result['message']}"
        lines.append(f"| {step['seq']} | {step['actor']} | {step['action']} | {step['status']} | {cell(detail)} |")
    lines += ["", "## 假设与实验", "", "假设为模型在候选提交前的解释，判定来自随后实际评测。", "",
              "| 候选 | 假设或目的 | 预期 | 实测状态 | 判定 |", "|---|---|---|---|---|"]
    for experiment in report["research"]["experiments"]:
        lines.append(f"| {experiment['candidate_id']} | {cell(experiment['hypothesis'] or experiment['purpose'])} | "
                     f"{cell(experiment['expected'])} | {experiment['result']['status']} | {experiment['verdict']} |")
    lines += ["", "## 候选", "", "| 候选 | 来源 | 父候选 | 开发验证 | 指标 | 改善 |", "|---|---|---|---|---|---|"]
    for candidate in report["candidates"]:
        evaluation = candidate["dev_evaluations"][-1]
        candidate_id = candidate["candidate_id"]
        lines.append(f"| [{candidate_id}](candidates/{candidate_id}.py) | {candidate['origin']} | "
                     f"{cell(candidate['parent_candidate_id'])} | {evaluation['status']} | {cell(metric(evaluation))} | {bool(evaluation['improved'])} |")
    lines += ["", "## 资源", "",
              f"- 请求 {summary['model_requests']} 次；候选 {summary['candidates_proposed']} 个，"
              f"通过 {summary['candidates_passed']} 个；AST 去重后 {summary['unique_ast_candidates']} 个。",
              f"- 时间：总计 {summary['wall_clock_s']}s；模型等待 {summary['model_wait_s']}s；开发验证 {summary['dev_evaluation_s']}s。",
              f"- Token：输入 {summary['input_tokens']}（含缓存 {summary['cached_input_tokens']}），输出 {summary['output_tokens']}。",
              f"- 按冻结单价估算 ¥{summary['estimated_cny']:.6f}；输入 ¥3/百万 token、输出 ¥12/百万 token，缓存按普通输入价估算。",
              "", "## 复现", "", f"```sh\n{report['reproduce']['run_again']}\n```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=ROOT / "backend/var/native-pilot-r2-20261114")
    parser.add_argument("--runs", type=Path, default=ROOT / "backend/var/runs")
    parser.add_argument("--tasks", type=Path, default=ROOT / "backend/var/tasks")
    args = parser.parse_args()
    manifest, comparison = read(args.pilot / "manifest.json"), read(args.pilot / "comparison.json")
    if comparison["status"] != "completed" or comparison["final_evaluation"] is not False:
        raise ValueError("expected a completed development-only comparison")
    audit = read(HERE / "protocol-audit.json")
    audited = {run["run_id"]: run for run in audit["rounds"]["second"]["runs"]}
    tasks = {task["task_id"]: task for task in manifest["tasks"]}
    price = manifest["pricing"]["price"]
    rates = [price[f"{name}_price_range"] for name in ("input", "output")]
    if manifest["price_currency"] != "CNY" or manifest["price_unit"] != "per 1M tokens" or any(lo != hi for lo, hi in rates):
        raise ValueError("expected fixed CNY rates per million tokens")
    input_rate, output_rate = (Decimal(str(rate[0])) for rate in rates)
    for name in ("manifest.json", "comparison.json"):
        copy_verified(args.pilot / name, HERE / name)
    summaries = []
    for item in comparison["runs"]:
        run_id = item["run_id"]
        source, destination = args.runs / run_id, HERE / run_id
        report = read(source / "report.json")
        if report["status"] != "completed" or report["final_evaluation"] is not None or report["outcome"]["final_evaluated"]:
            raise ValueError(f"unexpected run state: {run_id}")
        if report["config"]["models"]["small"]["model"] != manifest["pricing"]["id"]:
            raise ValueError(f"frozen price model mismatch: {run_id}")
        expected_names = {f"{candidate['candidate_id']}.py" for candidate in report["candidates"]}
        if {path.name for path in (source / "candidates").glob("*.py")} != expected_names:
            raise ValueError(f"candidate inventory differs from report: {run_id}")
        copy_verified(source / "report.json", destination / "report.json")
        for candidate in report["candidates"]:
            filename = f"{candidate['candidate_id']}.py"
            copy_verified(source / "candidates" / filename, destination / "candidates" / filename, candidate["code_sha256"])
        if report["task"]["family"] == "algotune":
            task_id = report["task"]["task_id"]
            copy_verified(args.tasks / task_id / "UPSTREAM_LICENSE.txt", destination / "UPSTREAM_LICENSE.txt",
                          tasks[task_id]["files"]["UPSTREAM_LICENSE.txt"]["sha256"])
        summary = summarize(report, audited[run_id], input_rate, output_rate)
        summaries.append(summary)
        (destination / "research.md").write_text(research_markdown(report, summary))
    total_fields = ("model_requests", "candidates_proposed", "candidates_passed", "unique_ast_candidates",
                    "best_dev_passed_cases", "dev_case_count", "input_tokens", "cached_input_tokens", "output_tokens",
                    "total_tokens", "candidate_files_exported_and_sha256_verified")
    total = {name: sum(run[name] for run in summaries) for name in total_fields}
    for name in ("wall_clock_s", "model_wait_s", "dev_evaluation_s", "container_startup_s", "estimated_cny"):
        total[name] = float(sum(Decimal(str(run[name])) for run in summaries))
    total.update(runs=len(summaries), final_evaluated_runs=sum(run["final_evaluated"] for run in summaries),
                 invalid_actions=sum(sum(run["invalid_actions"].values()) for run in summaries))
    result = {"scope": "development pilot; final data not evaluated", "comparison_id": comparison["comparison_id"],
              "runs": summaries, "total": total,
              "pricing": {"source": manifest["price_source"], "currency": "CNY", "unit": manifest["price_unit"],
                          "input": float(input_rate), "output": float(output_rate),
                          "method": "standard input/output rates; cached input charged at standard input rate; estimate, not invoice"},
              "metric_definitions": {"accepted_dev_metric": "latest development metric of the actual selected candidate",
                                     "highest_raw_dev_speedup": "maximum recorded speedup across all candidate development evaluations, irrespective of selection",
                                     "best_dev_passed_cases": "passed development cases of the selected candidate"}}
    (HERE / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(total, ensure_ascii=False))


if __name__ == "__main__":
    main()
