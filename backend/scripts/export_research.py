"""Export representative research runs as deliverable bundles into docs/research/, with an index.

    uv run python scripts/export_research.py

Runs are chosen by rule, not by hand-picked ids: each case shows one thing the Research Agent PRD asks to see,
including a run without improvement and a run whose final test failed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from routeevo import cli, compare, db, narrative, report

OUT = Path(__file__).resolve().parents[2] / "docs" / "research"


def learn_run(task: str, label: str = "formal A learning") -> str:
    return db.one("SELECT run_id FROM runs WHERE mode = 'learn' AND task_id = ? AND json_extract(config_json, '$.label') = ?"
                  " ORDER BY started_at LIMIT 1", (task, label))["run_id"]


def comparison_runs(prefix: str) -> dict | None:
    row = next((r for r in db.all_rows("SELECT comparison_id, label FROM comparisons WHERE status != 'running' ORDER BY created_at DESC")
                if (r["label"] or "").startswith(prefix)), None)
    return compare.summarize(row["comparison_id"]) if row else None


def pick_cases() -> list[tuple[str, str, str]]:
    cases = [(learn_run("A-01"), "反馈驱动的修正链（第一版）",
              "Qwen 的第一个假设被实测反驳（0.90×），第二个候选输出格式错误；连续两次未达标触发升级，GPT 读到具体失败反馈后提出新假设并得到支持。")]
    # version 2: a learning run that re-validated known programs, raised its target and beat the best of them
    best_gain, chosen = 0.0, None
    for r in db.all_rows("SELECT run_id FROM runs WHERE mode = 'learn' AND json_extract(config_json, '$.label') LIKE 'reuse A learning%'"
                         " AND status = 'completed' ORDER BY started_at"):
        rep = report.build(r["run_id"])
        raised = next((st for st in rep["steps"] if st["action"] == "set_target"), None)
        won = [e for e in rep["research"]["experiments"] if e["kind"] == "model" and e["verdict"] == "supported"]
        if raised and won:
            gain = max(e["result"]["speedup"] for e in won) - raised["result"]["best_dev_speedup"]
            if gain > best_gain:
                best_gain, chosen = gain, (rep, raised, won)
    if chosen:
        rep, raised, won = chosen
        cases.append((rep["run_id"], "站在已知最佳上继续研究（第二版）",
                      f"{rep['task']['task_id']}：程序先复验经验中的已验证程序，最好的 {raised['result']['best_candidate_id']} 已达 "
                      f"{raised['result']['best_dev_speedup']:.2f}×；学习运行把目标提高到 {raised['result']['run_target_speedup']:g}×，"
                      f"模型以它为起点提出 {won[-1]['candidate_id']}，开发数据 {won[-1]['result']['speedup']:.2f}×，假设得到支持。"))
    cases.append((learn_run("A-05"), "没有验证出改进（第一版）",
                   "高基数工作负载上 Qwen 两个、GPT 一个候选都正确但更慢（0.80—0.83×），三个假设均被反驳；预算耗尽后交付初始程序，结论是“没有验证出改进”。"))
    held = comparison_runs("D final held-out · reuse") or comparison_runs("B dev comparison · reuse")
    if held:
        new = held["snapshot_b"]
        reused = next((r for t in held["tasks"] for r in held["per_task"][t][new]["runs"]
                       if r["goal_met"] and r["model_requests"] == 0 and r.get("best_from_reuse")), None)
        if reused:
            cases.append((reused["run_id"], "复验已验证程序直接达标（第二版留出）",
                          f"{held['tasks'][0][0]} 批留出任务、读取 {new}：程序复验经验中条件最接近的已验证程序，不调用任何模型即达标并交付。"))
    # a run that met the goal on dev data but whose frozen candidate failed the final test's strict rule
    for c in (held, comparison_runs("C final held-out")):
        if not c:
            continue
        missed = next((r for t in c["tasks"] for s in (c["snapshot_a"], c["snapshot_b"]) for r in c["per_task"][t][s]["runs"]
                       if r["stop_reason"] == "goal_reached" and not r["goal_met"]), None)
        if missed:
            cases.append((missed["run_id"], "开发达标、最终测试未达标",
                          "开发数据上已达标并停止；冻结候选在隐藏最终数据上正确，但没有满足“全部样本快于基线且 ≥ 1.10×”，按规则如实记为未达标。"))
            break
    return cases


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rows = ["# 研究成果样例", "",
            "由 `backend/scripts/export_research.py` 按规则从正式运行中选出并导出，每个目录是一份完整交付："
            "研究记录（`README.md`：研究任务、过程、假设与实验、最终测试、资源、复现）、最佳程序 `best.py`、全部候选、"
            "原始模型请求与回复 `model_calls/`、结构化报告 `report.json` 和复核脚本 `reproduce.sh`。"
            "任意一次运行都可以用 `uv run routeevo export-run <run_id> --bundle <目录>` 导出。", "",
            "| 案例 | 任务 · 读取快照 | 结论 | 请求 · 费用 | 说明 |", "|---|---|---|---|---|"]
    for run_id, title, why in pick_cases():
        rep = report.build(run_id)
        cli.export_bundle(run_id, OUT / run_id, narrative.run_markdown(run_id))
        u = rep["usage"]["total"]
        rows.append(f"| [{title}]({run_id}/README.md) | {rep['task']['task_id']} · {rep['snapshot_id']} | {rep['outcome']['summary']} | "
                    f"{rep['iterations']['model_requests']} 次 · {'$%.3f' % u['cost_usd'] if u['cost_usd'] is not None else '未知'} | {why} |")
    (OUT / "README.md").write_text("\n".join(rows) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
